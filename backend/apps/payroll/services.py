import calendar
import hashlib
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.attendance.services import holiday_dates_for, leave_index, leave_dicts, load_attendance_map, materialize_employee, office_now
from apps.common.audit import audit
from apps.common.dates import month_bounds
from apps.common.exceptions import BusinessError
from apps.common.money import D, json_safe, money
from apps.employees.services import employees_for_payroll, resolve_weekly_offs
from apps.organization.models import OfficeSettings
from apps.payroll.engine import calculate_pay, totals_from_lines
from apps.payroll.models import (
    AdvanceRecovery,
    Bonus,
    Deduction,
    PayrollLineItem,
    PayrollPeriod,
    PayrollRecord,
    SalaryAdvance,
    SalaryPayment,
)


def policy_from(office):
    return {
        "salary_divisor_mode": office.salary_divisor_mode,
        "fixed_salary_divisor": office.fixed_salary_divisor,
        "standard_work_minutes": office.standard_work_minutes,
        "overtime_multiplier": office.overtime_multiplier,
        "holiday_work_counts_as_overtime": office.holiday_work_counts_as_overtime,
        "unpaid_leave_deduction_enabled": office.unpaid_leave_deduction_enabled,
        "absence_deduction_enabled": office.absence_deduction_enabled,
        "late_penalty_enabled": office.late_penalty_enabled,
        "late_penalty_mode": office.late_penalty_mode,
        "late_penalty_amount": office.late_penalty_amount,
        "daily_wage_pays_weekly_off": office.daily_wage_pays_weekly_off,
        "daily_wage_pays_holiday": office.daily_wage_pays_holiday,
        "daily_wage_pays_paid_leave": office.daily_wage_pays_paid_leave,
    }


def policy_fingerprint(office):
    payload = "|".join(str(json_safe(policy_from(office))[key]) for key in sorted(policy_from(office)))
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def mark_period_stale(year, month):
    PayrollPeriod.objects.filter(
        year=year,
        month=month,
        status__in=[PayrollPeriod.Status.CALCULATED, PayrollPeriod.Status.APPROVED, PayrollPeriod.Status.REOPENED],
    ).update(needs_recalculation=True)


def plan_advances(employee):
    total = Decimal("0")
    plan = []
    for advance in SalaryAdvance.objects.filter(employee=employee, status=SalaryAdvance.Status.OPEN).order_by("issued_date", "id"):
        take = advance.remaining if not advance.monthly_recovery else min(advance.remaining, advance.monthly_recovery)
        take = money(take)
        if take > 0:
            plan.append({"id": advance.id, "amount": format(take, "f")})
            total += take
    return money(total), plan


def _employee_input(employee, year, month):
    return {
        "salary_type": employee.salary_type,
        "basic_salary": employee.basic_salary,
        "daily_rate": employee.daily_rate,
        "hourly_rate": employee.hourly_rate,
        "allowance_lines": [
            {"label": allowance.name, "amount": allowance.amount}
            for allowance in employee.allowances.filter(is_active=True)
        ],
        "joining_date": employee.joining_date,
        "exit_date": employee.exit_date,
        "year": year,
        "month": month,
    }


def build_facts(employee, year, month, today, office):
    start, end = month_bounds(year, month)
    attendance = load_attendance_map([employee.id], start, end).get(employee.id, {})
    plain = {
        day: {
            "status": item["status"],
            "late_minutes": item["late_minutes"],
            "early_departure_minutes": item["early_departure_minutes"],
            "working_minutes": item["working_minutes"],
            "overtime_minutes": item["overtime_minutes"],
            "is_incomplete": item["is_incomplete"],
        }
        for day, item in attendance.items()
    }
    leaves = leave_dicts(leave_index([employee.id], start, end).get(employee.id, []))
    from apps.payroll.engine import build_month_facts

    return build_month_facts(
        year=year,
        month=month,
        joining_date=employee.joining_date,
        exit_date=employee.exit_date,
        weekly_off_days=resolve_weekly_offs(employee, office),
        holiday_dates=holiday_dates_for(employee, start, end),
        attendance=plain,
        leaves=leaves,
        today=today,
    )


def preview_employee(employee, year, month, today=None, office=None, persist_attendance=False):
    office = office or OfficeSettings.load()
    today = today or office_now(office).date()
    if persist_attendance:
        materialize_employee(employee, year, month, today)
    facts, warnings = build_facts(employee, year, month, today, office)
    advance_total, advance_plan = plan_advances(employee)
    bonuses = [
        {"label": item.label, "amount": item.amount}
        for item in Bonus.objects.filter(employee=employee, year=year, month=month)
    ]
    deductions = [
        {"label": item.label, "amount": item.amount}
        for item in Deduction.objects.filter(employee=employee, year=year, month=month)
    ]
    result = calculate_pay(
        policy=policy_from(office),
        employee=_employee_input(employee, year, month),
        facts=facts,
        today=today,
        extras={"bonuses": bonuses, "deductions": deductions, "advances": advance_total},
        warnings=warnings,
    )
    result["advance_plan"] = advance_plan
    result["facts"] = facts
    return result


def _manual_dicts(record):
    if record is None:
        return []
    return [
        {
            "kind": item.kind,
            "code": item.code,
            "label": item.label,
            "amount": item.amount,
            "is_manual": True,
            "notes": item.notes,
            "reason": item.reason,
        }
        for item in record.line_items.filter(is_manual=True)
    ]


def refresh_payment_status(record):
    paid = money(sum((payment.amount for payment in record.payments.all()), Decimal("0")))
    record.amount_paid = paid
    if paid > 0:
        latest = record.payments.order_by("-paid_on", "-id").first()
        record.payment_date = latest.paid_on if latest else record.payment_date
        record.payment_method = latest.method if latest else record.payment_method
        record.payment_reference = latest.reference if latest else record.payment_reference
    if record.period.status != PayrollPeriod.Status.FINALIZED:
        record.payment_status = PayrollRecord.PaymentStatus.PENDING
    elif record.net_salary <= 0 or paid >= record.net_salary:
        record.payment_status = PayrollRecord.PaymentStatus.PAID
    elif paid <= 0:
        record.payment_status = PayrollRecord.PaymentStatus.UNPAID
    else:
        record.payment_status = PayrollRecord.PaymentStatus.PARTIALLY_PAID
    record.save(update_fields=["amount_paid", "payment_status", "payment_date", "payment_method", "payment_reference", "updated_at"])
    return record


def _apply_result(record, result, manual_lines):
    components = result["components"]
    counts = result["counts"]
    lines = list(result["lines"]) + list(manual_lines)
    totals = totals_from_lines(lines)
    manual_deductions = sum((D(item["amount"]) for item in manual_lines if item["kind"] == "deduction"), Decimal("0"))
    manual_earnings = sum((D(item["amount"]) for item in manual_lines if item["kind"] == "earning"), Decimal("0"))
    record.salary_type = result["salary_type"]
    record.scheduled_working_days = counts["scheduled_working_days"]
    record.present_days = counts["present_days"]
    record.absent_days = counts["absent_days"]
    record.half_days = counts["half_days"]
    record.paid_leave_days = counts["paid_leave_days"]
    record.unpaid_leave_days = counts["unpaid_leave_days"]
    record.weekly_offs = counts["weekly_offs"]
    record.public_holidays = counts["public_holidays"]
    record.late_count = counts["late_count"]
    record.late_minutes = counts["late_minutes"]
    record.early_departures = counts["early_departures"]
    record.working_hours = counts["working_hours"]
    record.overtime_hours = counts["overtime_hours"]
    record.attendance_percentage = counts["attendance_percentage"]
    record.basic_salary = components["basic_salary"]
    record.allowances_total = components["allowances_total"]
    record.bonuses_total = components["bonuses_total"]
    record.overtime_pay = components["overtime_pay"]
    record.approved_deductions = components["approved_deductions"]
    record.unpaid_leave_deduction = components["unpaid_leave_deduction"]
    record.attendance_deduction = components["attendance_deduction"]
    record.late_penalty = components["late_penalty"]
    record.advances_total = components["advances_total"]
    record.other_adjustments = money(manual_deductions - manual_earnings)
    record.gross_salary = totals["gross_salary"]
    record.total_deductions = totals["total_deductions"]
    record.net_salary = totals["net_salary"]
    record.breakdown = json_safe(
        {
            "counts": counts,
            "components": components,
            "warnings": result["warnings"],
            "formula": result["formula"],
            "advance_plan": result.get("advance_plan", []),
            "lines": lines,
        }
    )
    record.calculated_at = timezone.now()
    record.save()
    record.line_items.filter(is_manual=False).delete()
    PayrollLineItem.objects.bulk_create(
        [
            PayrollLineItem(
                record=record,
                kind=line["kind"],
                code=line["code"],
                label=line["label"],
                amount=money(line["amount"]),
                is_manual=False,
            )
            for line in result["lines"]
        ]
    )
    refresh_payment_status(record)


@transaction.atomic
def calculate_period(*, period, actor, request=None):
    if period.status == PayrollPeriod.Status.FINALIZED:
        raise BusinessError("This payroll is finalized. Reopen it with a reason before recalculating.")
    office = OfficeSettings.load()
    today = office_now(office).date()
    employees = list(employees_for_payroll(period.year, period.month))
    for employee in employees:
        materialize_employee(employee, period.year, period.month, today, actor=actor)
        result = preview_employee(employee, period.year, period.month, today=today, office=office)
        record, _created = PayrollRecord.objects.get_or_create(period=period, employee=employee)
        manual = _manual_dicts(record)
        _apply_result(record, result, manual)
    period.status = PayrollPeriod.Status.CALCULATED
    period.divisor_mode = office.salary_divisor_mode
    period.policy_fingerprint = policy_fingerprint(office)
    period.needs_recalculation = False
    period.calculated_at = timezone.now()
    period.calculated_by = actor
    period.approved_at = None
    period.approved_by = None
    period.save()
    audit(
        actor=actor,
        action="payroll.calculate",
        instance=period,
        summary=f"Calculated payroll for {calendar.month_name[period.month]} {period.year}.",
        request=request,
    )
    return period


def _require_current_policy(period):
    office = OfficeSettings.load()
    if period.policy_fingerprint and period.policy_fingerprint != policy_fingerprint(office):
        raise BusinessError("Salary policy changed after this calculation. Recalculate payroll before continuing.")
    if period.needs_recalculation:
        raise BusinessError("Attendance, leave, or pay inputs changed. Recalculate payroll before continuing.")


@transaction.atomic
def approve_period(*, period, actor, request=None):
    if period.status != PayrollPeriod.Status.CALCULATED:
        raise BusinessError("Only a calculated payroll can be approved.")
    _require_current_policy(period)
    period.status = PayrollPeriod.Status.APPROVED
    period.approved_at = timezone.now()
    period.approved_by = actor
    period.save()
    audit(actor=actor, action="payroll.approve", instance=period, summary=f"Approved payroll for {calendar.month_name[period.month]} {period.year}.", request=request)
    from apps.notifications.services import notify_payroll_approved

    notify_payroll_approved(period)
    return period


@transaction.atomic
def finalize_period(*, period, actor, request=None):
    if period.status != PayrollPeriod.Status.APPROVED:
        raise BusinessError("Approve the payroll preview before finalizing it.")
    period = PayrollPeriod.objects.select_for_update().get(pk=period.pk)
    _require_current_policy(period)
    records = list(PayrollRecord.objects.select_for_update().filter(period=period).select_related("employee"))
    for record in records:
        if record.advances_applied:
            continue
        plan = (record.breakdown or {}).get("advance_plan") or []
        for item in plan:
            advance = SalaryAdvance.objects.select_for_update().get(pk=item["id"], employee=record.employee)
            take = money(item["amount"])
            if advance.status != SalaryAdvance.Status.OPEN or advance.remaining < take:
                raise BusinessError("An advance balance changed after calculation. Recalculate payroll before finalizing.")
            AdvanceRecovery.objects.create(payroll_record=record, advance=advance, amount=take)
            advance.remaining = money(D(advance.remaining) - take)
            if advance.remaining <= 0:
                advance.remaining = money(0)
                advance.status = SalaryAdvance.Status.RECOVERED
            advance.save(update_fields=["remaining", "status"])
        record.advances_applied = True
        record.save(update_fields=["advances_applied", "updated_at"])
    period.status = PayrollPeriod.Status.FINALIZED
    period.finalized_at = timezone.now()
    period.finalized_by = actor
    period.save()
    for record in PayrollRecord.objects.filter(period=period):
        refresh_payment_status(record)
    audit(
        actor=actor,
        action="payroll.finalize",
        instance=period,
        summary=f"Finalized payroll for {calendar.month_name[period.month]} {period.year}.",
        request=request,
    )
    return period


@transaction.atomic
def reopen_period(*, period, actor, reason, request=None):
    if period.status != PayrollPeriod.Status.FINALIZED:
        raise BusinessError("Only a finalized payroll can be reopened.")
    if len((reason or "").strip()) < 3:
        raise BusinessError("Enter a reason for reopening payroll.")
    for recovery in AdvanceRecovery.objects.select_related("advance").filter(payroll_record__period=period):
        advance = recovery.advance
        advance.remaining = money(D(advance.remaining) + D(recovery.amount))
        advance.status = SalaryAdvance.Status.OPEN
        advance.save(update_fields=["remaining", "status"])
        recovery.delete()
    PayrollRecord.objects.filter(period=period).update(advances_applied=False)
    period.status = PayrollPeriod.Status.REOPENED
    period.reopen_reason = reason.strip()
    period.needs_recalculation = True
    period.save()
    audit(
        actor=actor,
        action="payroll.reopen",
        instance=period,
        summary=f"Reopened payroll for {calendar.month_name[period.month]} {period.year}.",
        reason=reason.strip(),
        request=request,
    )
    return period


@transaction.atomic
def adjust_record(*, record, kind, label, amount, reason, actor, request=None):
    if record.period.status == PayrollPeriod.Status.FINALIZED:
        raise BusinessError("This payroll is finalized. Reopen it before adding an adjustment.")
    if len((reason or "").strip()) < 3:
        raise BusinessError("Enter a reason for the adjustment.")
    if kind not in {PayrollLineItem.Kind.EARNING, PayrollLineItem.Kind.DEDUCTION}:
        raise BusinessError("Adjustment kind must be earning or deduction.")
    value = money(amount)
    if value <= 0:
        raise BusinessError("Adjustment amount must be greater than zero.")
    PayrollLineItem.objects.create(
        record=record,
        kind=kind,
        code=f"manual_{timezone.now().strftime('%H%M%S%f')}",
        label=label.strip() or "Manual adjustment",
        amount=value,
        is_manual=True,
        reason=reason.strip(),
    )
    lines = [
        {"kind": item.kind, "amount": item.amount}
        for item in record.line_items.all()
    ]
    totals = totals_from_lines(lines)
    manual = record.line_items.filter(is_manual=True)
    record.other_adjustments = money(
        sum((item.amount for item in manual if item.kind == "deduction"), Decimal("0"))
        - sum((item.amount for item in manual if item.kind == "earning"), Decimal("0"))
    )
    record.gross_salary = totals["gross_salary"]
    record.total_deductions = totals["total_deductions"]
    record.net_salary = totals["net_salary"]
    record.save()
    refresh_payment_status(record)
    if record.period.status == PayrollPeriod.Status.APPROVED:
        record.period.status = PayrollPeriod.Status.CALCULATED
        record.period.approved_at = None
        record.period.approved_by = None
        record.period.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])
    audit(
        actor=actor,
        action="payroll.adjust",
        instance=record,
        summary=f"Adjusted {record.employee.full_name}'s {calendar.month_name[record.period.month]} salary.",
        changes={"kind": kind, "label": label, "amount": format(value, "f")},
        reason=reason.strip(),
        request=request,
    )
    return record


@transaction.atomic
def record_payment(*, record, amount, paid_on, method, reference, notes, actor, request=None):
    if record.period.status != PayrollPeriod.Status.FINALIZED:
        raise BusinessError("Record payments only after payroll is finalized.")
    value = money(amount)
    if value <= 0:
        raise BusinessError("Payment amount must be greater than zero.")
    if record.net_salary < 0:
        raise BusinessError("This net salary is negative. Add an audited adjustment before recording a payment.")
    already = money(sum((payment.amount for payment in record.payments.all()), Decimal("0")))
    if already + value > record.net_salary:
        raise BusinessError("This payment would exceed the net salary.")
    payment = SalaryPayment.objects.create(
        record=record,
        amount=value,
        paid_on=paid_on,
        method=method,
        reference=reference or "",
        notes=notes or "",
        recorded_by=actor,
    )
    refresh_payment_status(record)
    audit(
        actor=actor,
        action="payroll.pay",
        instance=payment,
        summary=f"Recorded a salary payment for {record.employee.full_name}.",
        changes={"amount": format(value, "f"), "method": method, "reference": reference or ""},
        request=request,
    )
    return payment


def slip_payload(record):
    office = OfficeSettings.load()
    employee = record.employee
    lines = [
        {"kind": item.kind, "code": item.code, "label": item.label, "amount": format(money(item.amount), "f"), "manual": item.is_manual, "reason": item.reason}
        for item in record.line_items.all()
    ]
    return {
        "company": {"name": office.company_name, "legal_name": office.legal_name, "currency": office.currency},
        "employee": {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "full_name": employee.full_name,
            "department": employee.department.name if employee.department_id else "",
            "job_title": employee.job_title.name if employee.job_title_id else "",
            "joining_date": employee.joining_date.isoformat(),
        },
        "period": {"year": record.period.year, "month": record.period.month, "label": f"{calendar.month_name[record.period.month]} {record.period.year}", "status": record.period.status},
        "attendance": {
            "scheduled_working_days": format(record.scheduled_working_days, "f"),
            "present_days": format(record.present_days, "f"),
            "absent_days": format(record.absent_days, "f"),
            "half_days": format(record.half_days, "f"),
            "paid_leave_days": format(record.paid_leave_days, "f"),
            "unpaid_leave_days": format(record.unpaid_leave_days, "f"),
            "weekly_offs": format(record.weekly_offs, "f"),
            "public_holidays": format(record.public_holidays, "f"),
            "late_count": record.late_count,
            "late_minutes": record.late_minutes,
            "early_departures": record.early_departures,
            "working_hours": format(record.working_hours, "f"),
            "overtime_hours": format(record.overtime_hours, "f"),
            "attendance_percentage": format(record.attendance_percentage, "f"),
        },
        "lines": lines,
        "gross_salary": format(money(record.gross_salary), "f"),
        "total_deductions": format(money(record.total_deductions), "f"),
        "net_salary": format(money(record.net_salary), "f"),
        "payment_status": record.payment_status,
        "amount_paid": format(money(record.amount_paid), "f"),
        "payment_date": record.payment_date.isoformat() if record.payment_date else None,
        "payment_method": record.payment_method,
        "payment_reference": record.payment_reference,
        "warnings": (record.breakdown or {}).get("warnings", []),
        "formula": (record.breakdown or {}).get("formula", []),
        "notes": record.notes,
    }


def month_label(year, month):
    return f"{calendar.month_name[month]} {year}"
