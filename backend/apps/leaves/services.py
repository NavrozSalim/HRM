from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.attendance.services import apply_leave_attendance, clear_system_leave, holiday_dates_for
from apps.common.audit import audit
from apps.common.exceptions import BusinessError
from apps.common.money import D, money
from apps.employees.services import can_review_leave, employed_on, resolve_weekly_offs
from apps.leaves.models import LeaveBalance, LeaveRequest, LeaveType
from apps.organization.models import OfficeSettings


def ensure_balances(employee, year=None):
    year = year or timezone.now().year
    for leave_type in LeaveType.objects.filter(is_active=True, tracks_balance=True):
        LeaveBalance.objects.get_or_create(
            employee=employee,
            leave_type=leave_type,
            year=year,
            defaults={"entitled": leave_type.annual_entitlement, "used": Decimal("0"), "pending": Decimal("0")},
        )


def _is_non_working(employee, day, office):
    if day.weekday() in resolve_weekly_offs(employee, office):
        return True
    return day in holiday_dates_for(employee, day, day)


def count_leave_days(employee, start, end, day_part):
    office = OfficeSettings.load()
    if end < start:
        raise BusinessError("The leave end date cannot be before the start date.")
    if day_part != LeaveRequest.DayPart.FULL:
        if start != end:
            raise BusinessError("Partial-day leave must start and end on the same date.")
        if not employed_on(employee, start) or _is_non_working(employee, start, office):
            raise BusinessError("Partial-day leave must fall on a scheduled working day.")
        return Decimal("0.50")
    total = Decimal("0")
    day = start
    while day <= end:
        if employed_on(employee, day) and not _is_non_working(employee, day, office):
            total += Decimal("1")
        day += timedelta(days=1)
    if total == 0:
        raise BusinessError("The selected dates do not include a working day.")
    return total


def overlaps(employee, start, end, day_part, exclude_id=None):
    qs = LeaveRequest.objects.filter(
        employee=employee,
        status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
        start_date__lte=end,
        end_date__gte=start,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    for other in qs:
        same_day_halves = (
            day_part != LeaveRequest.DayPart.FULL
            and other.day_part != LeaveRequest.DayPart.FULL
            and day_part != other.day_part
            and start == end == other.start_date == other.end_date
        )
        if same_day_halves:
            continue
        return True
    return False


def _balance_for(employee, leave_type, year):
    if not leave_type.tracks_balance:
        return None
    balance, _created = LeaveBalance.objects.select_for_update().get_or_create(
        employee=employee,
        leave_type=leave_type,
        year=year,
        defaults={"entitled": leave_type.annual_entitlement},
    )
    return balance


def _reserve(balance, days):
    available = balance.entitled - balance.used - balance.pending
    if days > available and not balance.leave_type.allow_negative:
        raise BusinessError(
            f"Only {money(available)} {balance.leave_type.name} day(s) are available. Requested {money(days)}."
        )
    balance.pending = money(D(balance.pending) + D(days))
    balance.save(update_fields=["pending", "updated_at"])


@transaction.atomic
def submit_leave(*, employee, leave_type, start, end, day_part, reason, document, actor, request=None):
    if leave_type.requires_document and not document:
        raise BusinessError(f"{leave_type.name} requires a supporting document.")
    if not reason or len(reason.strip()) < 3:
        raise BusinessError("Enter a leave reason.")
    days = count_leave_days(employee, start, end, day_part)
    if overlaps(employee, start, end, day_part):
        raise BusinessError("This request overlaps an existing pending or approved leave.")
    balance = _balance_for(employee, leave_type, start.year)
    if balance is not None:
        _reserve(balance, days)
    leave = LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start,
        end_date=end,
        day_part=day_part,
        total_days=days,
        reason=reason.strip(),
        document=document,
        status=LeaveRequest.Status.PENDING,
    )
    audit(
        actor=actor,
        action="leave.submit",
        instance=leave,
        summary=f"{employee.full_name} requested {days} day(s) of {leave_type.name}.",
        request=request,
    )
    from apps.notifications.services import notify_leave_submitted

    notify_leave_submitted(leave)
    return leave


@transaction.atomic
def decide_leave(*, leave, actor, approve, note="", request=None):
    if leave.status != LeaveRequest.Status.PENDING:
        raise BusinessError("Only a pending request can be approved or rejected.")
    if not can_review_leave(actor, leave.employee):
        raise BusinessError("You cannot review this leave request.", status_code=403)
    from apps.payroll.models import PayrollPeriod

    if approve and PayrollPeriod.objects.filter(
        year__gte=leave.start_date.year,
        status=PayrollPeriod.Status.FINALIZED,
    ).exists():
        # Block only when a covered month is finalized.
        cursor = leave.start_date
        while cursor <= leave.end_date:
            if PayrollPeriod.objects.filter(year=cursor.year, month=cursor.month, status=PayrollPeriod.Status.FINALIZED).exists():
                raise BusinessError("Leave overlaps a finalized payroll month. Reopen payroll before approving it.")
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1, day=1)
    balance = _balance_for(leave.employee, leave.leave_type, leave.start_date.year) if leave.leave_type.tracks_balance else None
    if balance is not None:
        balance.pending = money(max(Decimal("0"), D(balance.pending) - D(leave.total_days)))
        if approve:
            balance.used = money(D(balance.used) + D(leave.total_days))
        balance.save(update_fields=["pending", "used", "updated_at"])
    leave.status = LeaveRequest.Status.APPROVED if approve else LeaveRequest.Status.REJECTED
    leave.review_note = note or ""
    leave.reviewed_by = actor
    leave.reviewed_at = timezone.now()
    leave.save()
    warnings = apply_leave_attendance(leave) if approve else []
    if approve:
        from apps.payroll.models import PayrollPeriod

        PayrollPeriod.objects.filter(
            year=leave.start_date.year,
            month__gte=leave.start_date.month,
            status__in=["calculated", "approved", "reopened"],
        ).update(needs_recalculation=True)
    audit(
        actor=actor,
        action="leave.approve" if approve else "leave.reject",
        instance=leave,
        summary=f"{leave.employee.full_name}'s {leave.leave_type.name} request was {'approved' if approve else 'rejected'}.",
        reason=note or "",
        request=request,
    )
    from apps.notifications.services import notify_leave_decision

    notify_leave_decision(leave)
    return leave, warnings


@transaction.atomic
def cancel_leave(*, leave, actor, request=None):
    if leave.status not in {LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED}:
        raise BusinessError("This request can no longer be cancelled.")
    is_owner = leave.employee.user_id == getattr(actor, "id", None)
    if leave.status == LeaveRequest.Status.APPROVED and not can_review_leave(actor, leave.employee):
        raise BusinessError("Approved leave can only be cancelled by HR or the department manager.", status_code=403)
    if leave.status == LeaveRequest.Status.PENDING and not (is_owner or can_review_leave(actor, leave.employee) or actor.role in {"super_admin", "management", "hr_manager"}):
        raise BusinessError("You cannot cancel this request.", status_code=403)
    from apps.payroll.models import PayrollPeriod

    if leave.status == LeaveRequest.Status.APPROVED and PayrollPeriod.objects.filter(
        year=leave.start_date.year, month=leave.start_date.month, status=PayrollPeriod.Status.FINALIZED
    ).exists():
        raise BusinessError("This leave is in a finalized payroll month and cannot be cancelled until payroll is reopened.")
    if leave.leave_type.tracks_balance:
        balance = _balance_for(leave.employee, leave.leave_type, leave.start_date.year)
        if leave.status == LeaveRequest.Status.PENDING:
            balance.pending = money(max(Decimal("0"), D(balance.pending) - D(leave.total_days)))
        else:
            balance.used = money(max(Decimal("0"), D(balance.used) - D(leave.total_days)))
        balance.save(update_fields=["pending", "used", "updated_at"])
    if leave.status == LeaveRequest.Status.APPROVED:
        clear_system_leave(leave.employee, leave.start_date, leave.end_date)
    leave.status = LeaveRequest.Status.CANCELLED
    leave.save(update_fields=["status", "updated_at"])
    audit(
        actor=actor,
        action="leave.cancel",
        instance=leave,
        summary=f"Cancelled {leave.employee.full_name}'s {leave.leave_type.name} request.",
        request=request,
    )
    return leave


@transaction.atomic
def adjust_balance(*, balance, entitled, actor, reason, request=None):
    if len((reason or "").strip()) < 3:
        raise BusinessError("Enter a reason for the balance change.")
    previous = balance.entitled
    balance.entitled = money(entitled)
    if balance.entitled < 0:
        raise BusinessError("Entitlement cannot be negative.")
    balance.save(update_fields=["entitled", "updated_at"])
    audit(
        actor=actor,
        action="leave.balance",
        instance=balance,
        summary=f"Updated {balance.employee.full_name}'s {balance.leave_type.name} entitlement.",
        changes={"entitled": {"from": str(previous), "to": str(balance.entitled)}},
        reason=reason.strip(),
        request=request,
    )
    return balance
