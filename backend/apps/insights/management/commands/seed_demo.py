from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.attendance.services import upsert_attendance
from apps.common.dates import month_bounds
from apps.employees.models import Employee, EmployeeAllowance
from apps.employees.services import record_event, resolve_weekly_offs
from apps.leaves.models import LeaveType
from apps.leaves.services import decide_leave, ensure_balances, submit_leave
from apps.notifications.services import generate_alerts
from apps.organization.models import Department, Holiday, JobTitle, OfficeLocation, OfficeSettings, Shift
from apps.payroll.models import Bonus, Deduction, PayrollPeriod, PayrollRecord, SalaryAdvance
from apps.payroll.services import approve_period, calculate_period, finalize_period, record_payment

User = get_user_model()
PASSWORD = "Harbor@12345"


class Command(BaseCommand):
    help = "Load synthetic Wesolucions demonstration data. This is not real employee information."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Erase existing data and load the demo again.")

    def handle(self, *args, **options):
        if Employee.objects.exists() and not options["reset"]:
            self.stdout.write("Demo data already exists. Run with --reset to replace it.")
            return
        if options["reset"]:
            call_command("flush", interactive=False)
        with transaction.atomic():
            admin = self._build()
        self.stdout.write(self.style.SUCCESS("Demo office is ready."))
        self.stdout.write(f"Sign in as admin / {PASSWORD}")
        self.stdout.write("Other demo accounts use the same password: hr.khan, accounts.noor, manager.reza, aisha.malik, bilal.qureshi")
        self.stdout.write(f"Super admin id: {admin.id}")

    def _build(self):
        office = OfficeSettings.load()
        office.company_name = "Wesolucions"
        office.legal_name = "Wesolucions"
        office.timezone = "Asia/Karachi"
        office.currency = "USD"
        office.default_weekly_off_days = [5, 6]
        office.salary_divisor_mode = OfficeSettings.DivisorMode.SCHEDULED
        office.unpaid_leave_deduction_enabled = True
        office.absence_deduction_enabled = False
        office.late_penalty_enabled = False
        office.self_checkin_enabled = True
        office.biometric_enabled = False
        office.half_day_threshold_minutes = 240
        office.monthly_late_warning_threshold = 3
        office.save()

        location = OfficeLocation.objects.create(name="Wesolucions Head Office", address="12 Example Wharf, Demo City", timezone="Asia/Karachi")
        general = Shift.objects.create(name="General day", start_time="09:00", end_time="17:00", break_minutes=60, grace_minutes=10, early_grace_minutes=10)
        morning = Shift.objects.create(name="Morning", start_time="07:00", end_time="15:00", break_minutes=45, grace_minutes=10, early_grace_minutes=10)
        night = Shift.objects.create(name="Night", start_time="22:00", end_time="06:00", break_minutes=60, grace_minutes=10, early_grace_minutes=10)

        admin = self._user("admin", "Amina", "Rahman", User.Role.SUPER_ADMIN, staff=True)
        hr = self._user("hr.khan", "Imran", "Khan", User.Role.HR_MANAGER)
        accountant = self._user("accounts.noor", "Noor", "Hassan", User.Role.ACCOUNTANT)
        reza_user = self._user("manager.reza", "Reza", "Karim", User.Role.DEPARTMENT_MANAGER)
        aisha_user = self._user("aisha.malik", "Aisha", "Malik", User.Role.EMPLOYEE)
        bilal_user = self._user("bilal.qureshi", "Bilal", "Qureshi", User.Role.EMPLOYEE)

        engineering = Department.objects.create(name="Engineering", code="ENG", location=location, manager=reza_user)
        finance = Department.objects.create(name="Finance", code="FIN", location=location)
        operations = Department.objects.create(name="Operations", code="OPS", location=location)
        people = Department.objects.create(name="People & Culture", code="PC", location=location, manager=hr)

        titles = {
            "lead": JobTitle.objects.create(name="Engineering Lead", department=engineering),
            "dev": JobTitle.objects.create(name="Software Developer", department=engineering),
            "analyst": JobTitle.objects.create(name="Finance Analyst", department=finance),
            "coordinator": JobTitle.objects.create(name="Operations Coordinator", department=operations),
            "partner": JobTitle.objects.create(name="People Partner", department=people),
        }
        Holiday.objects.create(name="Office Foundation Day", date=date(2026, 10, 2), notes="Synthetic holiday for the demo office.")

        for name, code, paid, tracks, days in [
            ("Casual leave", "CL", True, True, 8),
            ("Sick leave", "SL", True, True, 8),
            ("Annual leave", "AL", True, True, 16),
            ("Unpaid leave", "UL", False, False, 0),
            ("Emergency leave", "EL", True, True, 3),
        ]:
            LeaveType.objects.create(name=name, code=code, is_paid=paid, tracks_balance=tracks, annual_entitlement=days, color="#0f766e" if paid else "#b45309")

        specs = [
            ("EMP-001", "Reza", "Karim", reza_user, engineering, titles["lead"], general, "monthly", 4500, date(2018, 3, 1), date(1988, 6, 2), Employee.Status.ACTIVE),
            ("EMP-002", "Aisha", "Malik", aisha_user, engineering, titles["dev"], general, "monthly", 3200, date(2020, 10, 15), date(1994, 10, 12), Employee.Status.ACTIVE),
            ("EMP-003", "Bilal", "Qureshi", bilal_user, engineering, titles["dev"], general, "monthly", 2800, date(2023, 2, 6), date(1996, 1, 20), Employee.Status.ACTIVE),
            ("EMP-004", "Chen", "Wei", None, engineering, titles["dev"], night, "monthly", 3600, date(2022, 7, 11), date(1993, 11, 3), Employee.Status.ACTIVE),
            ("EMP-005", "Diego", "Alvarez", None, engineering, titles["dev"], general, "daily", 0, date(2025, 5, 1), date(1998, 4, 9), Employee.Status.ACTIVE),
            ("EMP-006", "Elena", "Petrova", None, finance, titles["analyst"], general, "monthly", 3400, date(2021, 9, 1), date(1991, 12, 28), Employee.Status.ACTIVE),
            ("EMP-007", "Farah", "Siddiqui", None, finance, titles["analyst"], general, "monthly", 3000, date(2024, 1, 15), date(1997, 8, 19), Employee.Status.ACTIVE),
            ("EMP-008", "Jonah", "Ellis", None, operations, titles["coordinator"], morning, "monthly", 2400, date(2023, 11, 1), date(1995, 3, 14), Employee.Status.ACTIVE),
            ("EMP-009", "Hana", "Suzuki", None, operations, titles["coordinator"], general, "hourly", 0, date(2025, 8, 4), date(1999, 5, 23), Employee.Status.ACTIVE),
            ("EMP-010", "Ivan", "Petrov", None, operations, titles["coordinator"], morning, "monthly", 2600, date(2022, 1, 10), date(1990, 2, 2), Employee.Status.ON_NOTICE),
            ("EMP-011", "Leila", "Haddad", None, people, titles["partner"], general, "monthly", 3100, date(2019, 4, 8), date(1992, 9, 30), Employee.Status.ACTIVE),
            ("EMP-012", "Maya", "Chen", None, people, titles["partner"], general, "monthly", 2200, date(2024, 1, 8), date(2000, 7, 7), Employee.Status.INACTIVE),
        ]
        employees = {}
        for code, first, last, user, department, title, shift, salary_type, basic, joined, born, status in specs:
            employee = Employee.objects.create(
                user=user,
                employee_code=code,
                first_name=first,
                last_name=last,
                email=f"{first}.{last}@example.com".lower(),
                phone=f"+1-555-01{code[-2:]}",
                address="Synthetic residential address",
                emergency_contact_name="Demo Contact",
                emergency_contact_phone="+1-555-0199",
                emergency_contact_relation="Sibling",
                department=department,
                job_title=title,
                location=location,
                joining_date=joined,
                date_of_birth=born,
                status=status,
                exit_date=date(2026, 8, 31) if status == Employee.Status.INACTIVE else None,
                shift=shift,
                salary_type=salary_type,
                basic_salary=basic if salary_type == "monthly" else 0,
                daily_rate=80 if salary_type == "daily" else 0,
                hourly_rate=18 if salary_type == "hourly" else 0,
                employment_type=Employee.EmploymentType.DAILY_WAGE if salary_type == "daily" else Employee.EmploymentType.HOURLY if salary_type == "hourly" else Employee.EmploymentType.FULL_TIME,
                bank_name="Example Bank",
                bank_account_name=f"{first} {last}",
                bank_account_number=f"00001111{code[-3:]}",
                bank_routing="EXAMPLE00",
                notes="Synthetic demonstration profile.",
            )
            if salary_type == "monthly":
                EmployeeAllowance.objects.create(employee=employee, name="Transport", amount=100)
            ensure_balances(employee, 2026)
            record_event(employee=employee, event_type="hired", summary=f"{employee.full_name} joined {department.name}.", actor=admin)
            employees[code] = employee

        unpaid = LeaveType.objects.get(code="UL")
        sick = LeaveType.objects.get(code="SL")
        casual = LeaveType.objects.get(code="CL")
        farah_leave = submit_leave(employee=employees["EMP-007"], leave_type=unpaid, start=date(2026, 9, 9), end=date(2026, 9, 9), day_part="full", reason="Unpaid personal day", document=None, actor=admin)
        decide_leave(leave=farah_leave, actor=admin, approve=True, note="Approved unpaid day")
        leila_leave = submit_leave(employee=employees["EMP-011"], leave_type=sick, start=date(2026, 9, 18), end=date(2026, 9, 18), day_part="full", reason="Synthetic sick day", document=None, actor=admin)
        decide_leave(leave=leila_leave, actor=admin, approve=True, note="Approved")

        skip = {
            ("EMP-007", date(2026, 9, 9)),
            ("EMP-011", date(2026, 9, 18)),
            ("EMP-008", date(2026, 9, 10)),
        }
        self._mark_month(employees, 2026, 9, admin, skip)
        upsert_attendance(employee=employees["EMP-002"], day=date(2026, 9, 2), actor=admin, check_in="09:30", check_out="17:00", reason="Correct demo lateness", allow_without_reason=False)
        upsert_attendance(employee=employees["EMP-002"], day=date(2026, 9, 8), actor=admin, check_in="09:22", check_out="17:00", reason="Second late arrival", allow_without_reason=False)
        upsert_attendance(employee=employees["EMP-003"], day=date(2026, 9, 3), actor=admin, check_in="09:00", check_out="16:00", reason="Left early for a booked appointment", allow_without_reason=False)
        upsert_attendance(employee=employees["EMP-009"], day=date(2026, 9, 4), actor=admin, check_in="09:00", check_out="19:00", reason="Hourly overtime example", allow_without_reason=False)

        Bonus.objects.create(employee=employees["EMP-007"], year=2026, month=9, label="Project bonus", amount=150, reason="Synthetic bonus", created_by=admin)
        Deduction.objects.create(employee=employees["EMP-006"], year=2026, month=9, label="Staff loan", amount=50, reason="Approved loan installment", created_by=admin)
        SalaryAdvance.objects.create(employee=employees["EMP-003"], amount=200, remaining=200, issued_date=date(2026, 9, 1), monthly_recovery=100, reason="Synthetic salary advance", created_by=admin)

        september = PayrollPeriod.objects.create(year=2026, month=9, notes="Demo September payroll")
        calculate_period(period=september, actor=admin)
        approve_period(period=september, actor=admin)
        finalize_period(period=september, actor=admin)
        for record in PayrollRecord.objects.filter(period=september).select_related("employee"):
            if record.employee.employee_code == "EMP-007":
                continue
            amount = record.net_salary / 2 if record.employee.employee_code == "EMP-008" else record.net_salary
            record_payment(record=record, amount=amount, paid_on=date(2026, 10, 2), method="bank", reference=f"PAY-2026-09-{record.employee.employee_code}", notes="Demo payment", actor=accountant)

        self._mark_month(employees, 2026, 10, admin, skip={("EMP-008", date(2026, 10, 6))}, last_day=date(2026, 10, 7))
        upsert_attendance(employee=employees["EMP-002"], day=date(2026, 10, 1), actor=admin, check_in="09:28", check_out="17:00", reason="October late example", allow_without_reason=False)
        upsert_attendance(employee=employees["EMP-002"], day=date(2026, 10, 8), actor=admin, check_in="09:40", source="self", allow_without_reason=True)
        upsert_attendance(employee=employees["EMP-003"], day=date(2026, 10, 8), actor=admin, check_in="09:02", source="self", allow_without_reason=True)
        october = PayrollPeriod.objects.create(year=2026, month=10, notes="October is calculated and waiting for approval.")
        calculate_period(period=october, actor=admin)
        submit_leave(employee=employees["EMP-002"], leave_type=casual, start=date(2026, 10, 20), end=date(2026, 10, 21), day_part="full", reason="Family visit", document=None, actor=aisha_user)
        generate_alerts(date(2026, 10, 8))
        return admin

    def _user(self, username, first, last, role, staff=False):
        user = User(username=username, first_name=first, last_name=last, email=f"{username}@example.com", role=role, is_staff=staff, is_superuser=staff)
        user.set_password(PASSWORD)
        user.save()
        return user

    def _mark_month(self, employees, year, month, actor, skip, last_day=None):
        start, end = month_bounds(year, month)
        if last_day:
            end = min(end, last_day)
        holidays = set(Holiday.objects.filter(date__range=(start, end), is_active=True).values_list("date", flat=True))
        office = OfficeSettings.load()
        for employee in employees.values():
            if employee.exit_date and employee.exit_date < start:
                continue
            offs = resolve_weekly_offs(employee, office)
            day = start
            while day <= end:
                if employee.joining_date <= day and (employee.exit_date is None or day <= employee.exit_date):
                    if day.weekday() not in offs and day not in holidays and (employee.employee_code, day) not in skip:
                        if employee.shift and (employee.shift.is_overnight or employee.shift.name == "Night"):
                            check_in, check_out = "22:00", "06:00"
                        elif employee.shift and employee.shift.name == "Morning":
                            check_in, check_out = "07:00", "15:00"
                        else:
                            check_in, check_out = "09:00", "17:00"
                        upsert_attendance(employee=employee, day=day, actor=actor, check_in=check_in, check_out=check_out, allow_without_reason=True)
                day += timedelta(days=1)
