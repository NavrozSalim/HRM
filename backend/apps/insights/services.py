from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.attendance.models import AttendanceRecord
from apps.attendance.services import leave_dicts, leave_index, load_attendance_map, office_now
from apps.common.dates import month_bounds
from apps.common.money import D, money
from apps.employees.services import WORKING_STATUSES, can_view_salary, resolve_weekly_offs, visible_employees
from apps.organization.models import Holiday, OfficeSettings
from apps.payroll.engine import build_month_facts
from apps.payroll.models import PayrollPeriod, PayrollRecord
from apps.payroll.services import month_label, preview_employee, slip_payload


def fact_status(fact):
    if fact["status"]:
        return fact["status"]
    if not fact["employed"]:
        return "not_employed"
    if fact["holiday"]:
        return "public_holiday"
    if fact["weekly_off"]:
        return "weekly_off"
    if D(fact["paid_leave"]) + D(fact["unpaid_leave"]) > 0:
        return "on_leave"
    if D(fact["absent"]) >= 1:
        return "absent"
    if fact["unmarked"]:
        return "unmarked"
    return "upcoming"


def facts_for_employees(employees, year, month, today, office):
    start, end = month_bounds(year, month)
    ids = [employee.id for employee in employees]
    attendance = load_attendance_map(ids, start, end)
    leaves = leave_index(ids, start, end)
    holidays = list(Holiday.objects.filter(is_active=True, date__range=(start, end)))
    bundled = {}
    for employee in employees:
        holiday_dates = {item.date for item in holidays if item.location_id in {None, employee.location_id}}
        plain = {}
        for day, item in attendance.get(employee.id, {}).items():
            plain[day] = {
                "status": item["status"],
                "late_minutes": item["late_minutes"],
                "early_departure_minutes": item["early_departure_minutes"],
                "working_minutes": item["working_minutes"],
                "overtime_minutes": item["overtime_minutes"],
                "is_incomplete": item["is_incomplete"],
            }
        facts, warnings = build_month_facts(
            year=year,
            month=month,
            joining_date=employee.joining_date,
            exit_date=employee.exit_date,
            weekly_off_days=resolve_weekly_offs(employee, office),
            holiday_dates=holiday_dates,
            attendance=plain,
            leaves=leave_dicts(leaves.get(employee.id, [])),
            today=today,
        )
        bundled[employee.id] = {"facts": facts, "warnings": warnings, "attendance": attendance.get(employee.id, {})}
    return bundled


def _upcoming(employees, today, field, anniversary=False):
    found = []
    window = [today + timedelta(days=offset) for offset in range(0, 15)]
    for employee in employees:
        value = getattr(employee, field)
        if not value:
            continue
        for candidate in window:
            if value.month == candidate.month and value.day == candidate.day:
                if anniversary and value.year >= candidate.year:
                    break
                found.append(
                    {
                        "employee_id": employee.id,
                        "full_name": employee.full_name,
                        "date": candidate.isoformat(),
                        "years": candidate.year - value.year if anniversary else None,
                    }
                )
                break
    return found


def build_dashboard(user, day, department_id=None):
    from apps.notifications.services import generate_alerts

    office = OfficeSettings.load()
    generate_alerts(day)
    employees = visible_employees(user).order_by("employee_code")
    if department_id:
        employees = employees.filter(department_id=department_id)
    roster = list(employees)
    scope = "personal" if user.role == "employee" else "department" if user.role == "department_manager" else "company"
    show_company_money = user.role in {"super_admin", "management", "accountant", "hr_manager"} and scope != "personal"
    bundled = facts_for_employees(roster, day.year, day.month, day, office) if roster else {}
    today_counts = {key: 0 for key in ("present", "absent", "on_leave", "late", "on_time", "early_departures", "incomplete", "not_checked_in", "weekly_off", "holiday")}
    working_minutes = 0
    status_counts = {}
    attended = Decimal("0")
    elapsed = 0
    for employee in roster:
        if employee.status not in WORKING_STATUSES:
            continue
        packet = bundled.get(employee.id)
        if not packet:
            continue
        fact = next((item for item in packet["facts"] if item["date"] == day), None)
        if fact is None or not fact["employed"]:
            continue
        status = fact_status(fact)
        status_counts[status] = status_counts.get(status, 0) + 1
        if status in {"present", "late", "half_day", "holiday_worked", "off_worked"}:
            today_counts["present"] += 1
        if status == "absent":
            today_counts["absent"] += 1
        if status == "on_leave":
            today_counts["on_leave"] += 1
        if fact["late"] or status == "late":
            today_counts["late"] += 1
        if status in {"present", "half_day"} and not fact["late"]:
            today_counts["on_time"] += 1
        if fact["early_minutes"] > 0:
            today_counts["early_departures"] += 1
        if fact["incomplete"] or status == "incomplete":
            today_counts["incomplete"] += 1
        if status == "unmarked":
            today_counts["not_checked_in"] += 1
        if status == "weekly_off":
            today_counts["weekly_off"] += 1
        if status in {"public_holiday", "holiday_worked"}:
            today_counts["holiday"] += 1
        working_minutes += fact["working_minutes"]
        for item in packet["facts"]:
            if item["scheduled"] and item["date"] <= day:
                elapsed += 1
                attended += D(item["present"]) + D(item["paid_leave"])
    active = sum(1 for employee in roster if employee.status == "active")
    inactive = sum(1 for employee in roster if employee.status != "active")
    from apps.leaves.models import LeaveRequest

    pending_leave = LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING, employee__in=roster).count()
    period = PayrollPeriod.objects.filter(year=day.year, month=day.month).first()
    records = PayrollRecord.objects.filter(period=period, employee__in=roster) if period else PayrollRecord.objects.none()
    payroll_total = None
    payroll_source = "hidden"
    if scope == "personal" and roster and can_view_salary(user, roster[0]):
        own = records.filter(employee=roster[0]).first()
        if own:
            payroll_total = format(money(own.net_salary), "f")
            payroll_source = own.period.status
        else:
            payroll_total = None
            payroll_source = "not_calculated"
    elif show_company_money:
        if records.exists():
            payroll_total = format(money(sum((record.net_salary for record in records), Decimal("0"))), "f")
            payroll_source = period.status if period else "not_calculated"
        else:
            payroll_total = "0.00"
            payroll_source = "not_calculated"
    unpaid_qs = PayrollRecord.objects.filter(
        employee__in=roster,
        period__status=PayrollPeriod.Status.FINALIZED,
        payment_status__in=[PayrollRecord.PaymentStatus.UNPAID, PayrollRecord.PaymentStatus.PARTIALLY_PAID],
    )
    unpaid_amount = sum(((record.net_salary - record.amount_paid) for record in unpaid_qs), Decimal("0")) if show_company_money or scope == "personal" else None
    late_trend = []
    for offset in range(13, -1, -1):
        trend_day = day - timedelta(days=offset)
        late_trend.append(
            {
                "date": trend_day.isoformat(),
                "late": AttendanceRecord.objects.filter(date=trend_day, employee__in=roster).filter(
                    Q(status=AttendanceRecord.Status.LATE)
                    | Q(status=AttendanceRecord.Status.HALF_DAY, late_minutes__gt=0)
                    | Q(status=AttendanceRecord.Status.INCOMPLETE, late_minutes__gt=0)
                ).count(),
            }
        )
    departments = (
        visible_employees(user).filter(status="active").values("department__name").annotate(total=Count("id")).order_by("department__name")
    )
    if department_id:
        departments = departments.filter(department_id=department_id)
    payroll_by_department = []
    if show_company_money and period:
        grouped = (
            records.values("employee__department__name")
            .annotate(total=Sum("net_salary"))
            .order_by("employee__department__name")
        )
        payroll_by_department = [
            {"department": item["employee__department__name"] or "Unassigned", "total": format(money(item["total"] or 0), "f")}
            for item in grouped
        ]
    from apps.common.models import AuditLog

    activity = AuditLog.objects.select_related("actor")
    if user.role == "accountant":
        activity = activity.filter(model_name__startswith="payroll")
    elif user.role not in {"super_admin", "management", "hr_manager"}:
        activity = activity.filter(actor=user)
    recent = [
        {
            "id": item.id,
            "summary": item.summary,
            "created_at": item.created_at.isoformat(),
            "actor": item.actor.display_name if item.actor_id else "System",
        }
        for item in activity[:8]
    ]
    return {
        "scope": scope,
        "company_name": office.company_name,
        "currency": office.currency,
        "filters": {"date": day.isoformat(), "department": department_id},
        "headcount": {"total": len(roster), "active": active, "inactive": inactive},
        "today": {**today_counts, "working_hours": format(money(D(working_minutes) / Decimal("60")), "f")},
        "month": {
            "label": month_label(day.year, day.month),
            "attendance_percentage": format(money((attended / Decimal(elapsed) * Decimal("100")) if elapsed else 0), "f"),
            "payroll_total": payroll_total,
            "payroll_source": payroll_source,
            "needs_recalculation": bool(period and period.needs_recalculation),
        },
        "pending_leave_requests": pending_leave,
        "unpaid_salaries": {
            "count": unpaid_qs.count() if show_company_money or scope == "personal" else 0,
            "amount": format(money(unpaid_amount or 0), "f") if unpaid_amount is not None else None,
        },
        "birthdays": _upcoming(roster, day, "date_of_birth"),
        "anniversaries": _upcoming(roster, day, "joining_date", anniversary=True),
        "charts": {
            "status_breakdown": [{"status": key, "total": value} for key, value in sorted(status_counts.items())],
            "department_headcount": [{"department": item["department__name"] or "Unassigned", "total": item["total"]} for item in departments],
            "late_trend": late_trend,
            "payroll_by_department": payroll_by_department,
        },
        "recent_activity": recent,
    }


def employee_monthly_report(employee, year, month, user):
    office = OfficeSettings.load()
    today = office_now(office).date()
    record = PayrollRecord.objects.filter(employee=employee, period__year=year, period__month=month).select_related("period").first()
    if record:
        source = record.period.status
        attendance = {
            "scheduled_working_days": format(record.scheduled_working_days, "f"),
            "present_days": format(record.present_days, "f"),
            "absent_days": format(record.absent_days, "f"),
            "late_count": record.late_count,
            "late_minutes": record.late_minutes,
            "half_days": format(record.half_days, "f"),
            "paid_leave_days": format(record.paid_leave_days, "f"),
            "unpaid_leave_days": format(record.unpaid_leave_days, "f"),
            "weekly_offs": format(record.weekly_offs, "f"),
            "public_holidays": format(record.public_holidays, "f"),
            "early_departures": record.early_departures,
            "working_hours": format(record.working_hours, "f"),
            "overtime_hours": format(record.overtime_hours, "f"),
            "attendance_percentage": format(record.attendance_percentage, "f"),
        }
        salary = slip_payload(record) if can_view_salary(user, employee) else None
        warnings = (record.breakdown or {}).get("warnings", [])
        counts = (record.breakdown or {}).get("counts", {})
        attendance["punctuality_percentage"] = counts.get("punctuality_percentage")
        attendance["consecutive_absences"] = counts.get("consecutive_absences", 0)
        stale = record.period.needs_recalculation and record.period.status != PayrollPeriod.Status.FINALIZED
    else:
        preview = preview_employee(employee, year, month, today=today, office=office)
        counts = preview["counts"]
        source = "preview"
        attendance = {key: (format(value, "f") if isinstance(value, Decimal) else value) for key, value in counts.items()}
        salary = None
        if can_view_salary(user, employee):
            salary = {
                "lines": [
                    {"kind": line["kind"], "label": line["label"], "amount": format(money(line["amount"]), "f"), "manual": False}
                    for line in preview["lines"]
                ],
                "gross_salary": format(preview["totals"]["gross_salary"], "f"),
                "total_deductions": format(preview["totals"]["total_deductions"], "f"),
                "net_salary": format(preview["totals"]["net_salary"], "f"),
                "payment_status": "preview",
                "warnings": preview["warnings"],
                "formula": preview["formula"],
            }
        warnings = preview["warnings"]
        stale = False
    return {
        "employee": {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "full_name": employee.full_name,
            "department": employee.department.name if employee.department_id else "",
            "job_title": employee.job_title.name if employee.job_title_id else "",
            "status": employee.status,
            "joining_date": employee.joining_date.isoformat(),
        },
        "period": {"year": year, "month": month, "label": month_label(year, month)},
        "source": source,
        "stale": stale,
        "attendance": attendance,
        "salary": salary,
        "warnings": warnings,
        "currency": office.currency,
    }


def company_monthly_report(user, year, month, department_id=None):
    employees = visible_employees(user).order_by("department__name", "employee_code")
    if department_id:
        employees = employees.filter(department_id=department_id)
    rows = [employee_monthly_report(employee, year, month, user) for employee in employees]
    departments = {}
    for row in rows:
        name = row["employee"]["department"] or "Unassigned"
        bucket = departments.setdefault(name, {"department": name, "employees": 0, "present_days": Decimal("0"), "absent_days": Decimal("0"), "net_salary": Decimal("0")})
        bucket["employees"] += 1
        bucket["present_days"] += D(row["attendance"].get("present_days") or 0)
        bucket["absent_days"] += D(row["attendance"].get("absent_days") or 0)
        if row["salary"]:
            bucket["net_salary"] += D(row["salary"].get("net_salary") or 0)
    return {
        "period": {"year": year, "month": month, "label": month_label(year, month)},
        "employees": rows,
        "departments": [
            {
                **bucket,
                "present_days": format(money(bucket["present_days"]), "f"),
                "absent_days": format(money(bucket["absent_days"]), "f"),
                "net_salary": format(money(bucket["net_salary"]), "f") if user.role in {"super_admin", "management", "hr_manager", "accountant"} else None,
            }
            for bucket in departments.values()
        ],
    }
