from decimal import Decimal

from django.db.models import Q

from apps.accounts.roles import ATTENDANCE, HR, OFFICE, PAYROLL_VIEW
from apps.common.exceptions import BusinessError
from apps.employees.models import Employee, EmploymentEvent


WORKING_STATUSES = ("active", "on_notice")
SALARY_FIELDS = {
    "salary_type",
    "basic_salary",
    "daily_rate",
    "hourly_rate",
    "bank_name",
    "bank_account_name",
    "bank_account_number",
    "bank_routing",
}


def visible_employees(user):
    qs = Employee.objects.select_related("department", "department__manager", "job_title", "shift", "location", "user")
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if user.role in OFFICE:
        return qs
    if user.role == "department_manager":
        return qs.filter(department__manager=user)
    return qs.filter(user=user)


def can_view_salary(user, employee):
    if user.role in PAYROLL_VIEW:
        return True
    return user.role == "employee" and employee.user_id == user.id


def can_manage_employee(user, employee=None):
    if user.role in HR:
        return True
    return False


def can_manage_attendance(user, employee):
    if user.role in HR:
        return True
    if user.role == "department_manager" and employee.department_id and employee.department.manager_id == user.id:
        return True
    return False


def can_review_leave(user, employee):
    if employee.user_id and employee.user_id == user.id:
        return False
    return can_manage_attendance(user, employee)


def next_employee_code():
    numbers = []
    for code in Employee.objects.values_list("employee_code", flat=True):
        if code.startswith("EMP-") and code[4:].isdigit():
            numbers.append(int(code[4:]))
    return f"EMP-{(max(numbers) if numbers else 0) + 1:03d}"


def resolve_weekly_offs(employee, office):
    if employee.weekly_off_days is not None:
        return {int(day) for day in employee.weekly_off_days}
    shift = employee.shift if employee.shift_id else None
    if shift is not None and shift.weekly_off_days is not None:
        return {int(day) for day in shift.weekly_off_days}
    return {int(day) for day in (office.default_weekly_off_days or [])}


def validate_weekdays(values, allow_null=False):
    if values is None:
        if allow_null:
            return None
        raise BusinessError("Choose weekly off days.")
    if not isinstance(values, list):
        raise BusinessError("Weekly off days must be a list of weekday numbers, Monday = 0 through Sunday = 6.")
    cleaned = []
    for value in values:
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise BusinessError("Weekly off days must be numbers from 0 to 6.") from exc
        if number < 0 or number > 6:
            raise BusinessError("Weekly off days must be numbers from 0 to 6.")
        if number not in cleaned:
            cleaned.append(number)
    return cleaned


def record_event(*, employee, event_type, summary, actor=None, reason="", from_value="", to_value=""):
    EmploymentEvent.objects.create(
        employee=employee,
        event_type=event_type,
        summary=summary[:255],
        from_value=str(from_value or "")[:255],
        to_value=str(to_value or "")[:255],
        reason=reason or "",
        actor=actor if getattr(actor, "is_authenticated", False) else None,
    )


def money_changed(old, new):
    return Decimal(old or 0) != Decimal(new or 0)


def employed_on(employee, day):
    if employee.joining_date > day:
        return False
    if employee.exit_date and employee.exit_date < day:
        return False
    return True


def employees_for_payroll(year, month):
    from apps.common.dates import month_bounds

    start, end = month_bounds(year, month)
    return (
        Employee.objects.select_related("department", "shift", "location", "job_title")
        .filter(joining_date__lte=end)
        .filter(Q(exit_date__isnull=True) | Q(exit_date__gte=start))
        .exclude(status__in=["inactive", "terminated"], exit_date__isnull=True)
    )
