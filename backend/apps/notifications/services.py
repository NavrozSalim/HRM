from datetime import timedelta

from django.db.models import Q

from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.attendance.services import office_now
from apps.employees.models import Employee
from apps.employees.services import WORKING_STATUSES, resolve_weekly_offs
from apps.notifications.models import Notification
from apps.organization.models import OfficeSettings
from apps.payroll.models import PayrollPeriod, PayrollRecord


def notify(*, recipient, category, title, body, link="", dedupe_key=None):
    if recipient is None or not recipient.is_active:
        return None
    if dedupe_key:
        notification, created = Notification.objects.get_or_create(
            recipient=recipient,
            dedupe_key=dedupe_key,
            defaults={"category": category, "title": title, "body": body, "link": link},
        )
        if not created and not notification.is_read:
            notification.category = category
            notification.title = title
            notification.body = body
            notification.link = link
            notification.save(update_fields=["category", "title", "body", "link"])
        return notification
    return Notification.objects.create(recipient=recipient, category=category, title=title, body=body, link=link)


def _roles(*roles):
    return User.objects.filter(role__in=roles, is_active=True)


def notify_leave_submitted(leave):
    recipients = list(_roles("super_admin", "management", "hr_manager"))
    if leave.employee.department_id and leave.employee.department.manager_id:
        recipients.append(leave.employee.department.manager)
    for recipient in recipients:
        if recipient.id == leave.employee.user_id:
            continue
        notify(
            recipient=recipient,
            category="leave",
            title="Leave request waiting for review",
            body=f"{leave.employee.full_name} requested {leave.leave_type.name} from {leave.start_date} to {leave.end_date}.",
            link="/leaves",
            dedupe_key=f"leave-pending-{leave.id}",
        )


def notify_leave_decision(leave):
    if not leave.employee.user_id:
        return
    decision = "approved" if leave.status == "approved" else "rejected"
    notify(
        recipient=leave.employee.user,
        category="leave",
        title=f"Leave {decision}",
        body=f"Your {leave.leave_type.name} request for {leave.start_date} to {leave.end_date} was {decision}.",
        link="/me",
        dedupe_key=f"leave-decision-{leave.id}-{decision}",
    )


def notify_payroll_approved(period):
    for recipient in _roles("super_admin", "management", "accountant"):
        notify(
            recipient=recipient,
            category="payroll",
            title="Payroll is ready to finalize",
            body=f"{period.month:02d}/{period.year} payroll has been approved and is waiting to be finalized.",
            link="/payroll",
            dedupe_key=f"payroll-approved-{period.id}",
        )


def generate_alerts(today=None):
    office = OfficeSettings.load()
    today = today or office_now(office).date()
    hr_users = list(_roles("super_admin", "management", "hr_manager"))
    late_count = AttendanceRecord.objects.filter(date=today, status=AttendanceRecord.Status.LATE).count()
    if late_count and late_count >= 1:
        for recipient in hr_users:
            notify(
                recipient=recipient,
                category="late",
                title="Late arrivals today",
                body=f"{late_count} employee(s) arrived late on {today.isoformat()}.",
                link="/attendance",
                dedupe_key=f"late-{today.isoformat()}",
            )
    incomplete = AttendanceRecord.objects.filter(date=today, is_incomplete=True).select_related("employee")
    incomplete_count = incomplete.count()
    if incomplete_count:
        for recipient in hr_users:
            notify(
                recipient=recipient,
                category="attendance",
                title="Missing check-outs",
                body=f"{incomplete_count} employee(s) checked in today and have not checked out.",
                link="/attendance",
                dedupe_key=f"incomplete-{today.isoformat()}",
            )
        for record in incomplete:
            if record.employee.user_id:
                notify(
                    recipient=record.employee.user,
                    category="attendance",
                    title="Check-out is missing",
                    body=f"You checked in on {today.isoformat()} and do not have a check-out yet.",
                    link="/me",
                    dedupe_key=f"self-incomplete-{record.employee_id}-{today.isoformat()}",
                )
    from apps.attendance.services import holiday_dates_for

    missing = 0
    for employee in Employee.objects.filter(status__in=WORKING_STATUSES).select_related("shift", "location", "department"):
        if employee.joining_date > today or (employee.exit_date and employee.exit_date < today):
            continue
        if today.weekday() in resolve_weekly_offs(employee, office):
            continue
        if today in holiday_dates_for(employee, today, today):
            continue
        if AttendanceRecord.objects.filter(employee=employee, date=today).exists():
            continue
        missing += 1
    if missing:
        for recipient in hr_users:
            notify(
                recipient=recipient,
                category="attendance",
                title="Unmarked attendance",
                body=f"{missing} active employee(s) have no attendance record for {today.isoformat()}.",
                link="/attendance",
                dedupe_key=f"unmarked-{today.isoformat()}",
            )
    from apps.leaves.models import LeaveRequest

    pending = LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING).count()
    if pending:
        for recipient in hr_users:
            notify(
                recipient=recipient,
                category="leave",
                title="Pending leave requests",
                body=f"{pending} leave request(s) are waiting for a decision.",
                link="/leaves",
                dedupe_key="pending-leave-summary",
            )
    waiting = PayrollPeriod.objects.filter(status=PayrollPeriod.Status.CALCULATED)
    for period in waiting:
        for recipient in _roles("super_admin", "management", "accountant", "hr_manager"):
            notify(
                recipient=recipient,
                category="payroll",
                title="Payroll awaiting approval",
                body=f"{period.month:02d}/{period.year} payroll has been calculated and is waiting for approval.",
                link="/payroll",
                dedupe_key=f"payroll-waiting-{period.id}",
            )
    unpaid = PayrollRecord.objects.filter(
        period__status=PayrollPeriod.Status.FINALIZED,
        payment_status__in=[PayrollRecord.PaymentStatus.UNPAID, PayrollRecord.PaymentStatus.PARTIALLY_PAID],
    )
    unpaid_count = unpaid.count()
    if unpaid_count:
        for recipient in _roles("super_admin", "management", "accountant"):
            notify(
                recipient=recipient,
                category="payroll",
                title="Salaries still unpaid",
                body=f"{unpaid_count} finalized salary record(s) are unpaid or only partly paid.",
                link="/payroll",
                dedupe_key="unpaid-salaries",
            )
    window = [today + timedelta(days=offset) for offset in range(0, 8)]
    birthdays = []
    anniversaries = []
    for employee in Employee.objects.filter(status__in=WORKING_STATUSES):
        if employee.date_of_birth and any(employee.date_of_birth.month == day.month and employee.date_of_birth.day == day.day for day in window):
            birthdays.append(employee.full_name)
        if employee.joining_date and employee.joining_date.year < today.year and any(
            employee.joining_date.month == day.month and employee.joining_date.day == day.day for day in window
        ):
            anniversaries.append(employee.full_name)
    if birthdays:
        for recipient in hr_users:
            notify(
                recipient=recipient,
                category="celebration",
                title="Upcoming birthdays",
                body="Birthdays this week: " + ", ".join(birthdays[:8]),
                link="/dashboard",
                dedupe_key=f"birthdays-{today.isocalendar()[1]}",
            )
    if anniversaries:
        for recipient in hr_users:
            notify(
                recipient=recipient,
                category="celebration",
                title="Work anniversaries",
                body="Anniversaries this week: " + ", ".join(anniversaries[:8]),
                link="/dashboard",
                dedupe_key=f"anniversaries-{today.isocalendar()[1]}",
            )
    return {"late": late_count, "incomplete": incomplete_count, "unmarked": missing, "pending_leave": pending}
