from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.attendance.models import AttendanceRecord
from apps.attendance.services import upsert_attendance
from apps.employees.models import Employee
from apps.organization.models import Department, OfficeSettings, Shift
from apps.payroll.models import PayrollPeriod, PayrollRecord
from apps.payroll.services import approve_period, calculate_period, finalize_period

User = get_user_model()


class PermissionAndLockTests(APITestCase):
    def setUp(self):
        OfficeSettings.load()
        self.shift = Shift.objects.create(name="Day", start_time="09:00", end_time="17:00", break_minutes=60, grace_minutes=10)
        self.engineering = Department.objects.create(name="Engineering", code="ENG")
        self.finance = Department.objects.create(name="Finance", code="FIN")
        self.admin = User.objects.create_user("admin2", password="Harbor@12345", role=User.Role.SUPER_ADMIN)
        self.accountant = User.objects.create_user("acct2", password="Harbor@12345", role=User.Role.ACCOUNTANT)
        self.manager = User.objects.create_user("mgr2", password="Harbor@12345", role=User.Role.DEPARTMENT_MANAGER)
        self.engineering.manager = self.manager
        self.engineering.save()
        self.staff_user = User.objects.create_user("staff2", password="Harbor@12345", role=User.Role.EMPLOYEE)
        self.other_user = User.objects.create_user("other2", password="Harbor@12345", role=User.Role.EMPLOYEE)
        self.staff = Employee.objects.create(
            user=self.staff_user, employee_code="T-1", first_name="Test", last_name="One", department=self.engineering,
            shift=self.shift, joining_date=date(2024, 1, 1), basic_salary=Decimal("1000"), salary_type="monthly",
        )
        self.other = Employee.objects.create(
            user=self.other_user, employee_code="T-2", first_name="Test", last_name="Two", department=self.finance,
            shift=self.shift, joining_date=date(2024, 1, 1), basic_salary=Decimal("2000"), salary_type="monthly",
        )

    def test_employee_cannot_read_another_salary_or_payroll(self):
        self.client.force_authenticate(self.staff_user)
        denied = self.client.get(f"/api/employees/{self.other.id}/")
        self.assertEqual(denied.status_code, 404)
        own = self.client.get(f"/api/employees/{self.staff.id}/")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.data["basic_salary"], "1000.00")
        payroll = self.client.get("/api/payroll/records/")
        self.assertEqual(payroll.status_code, 200)
        self.assertEqual(payroll.data["count"], 0)

    def test_accountant_cannot_change_office_policy(self):
        self.client.force_authenticate(self.accountant)
        response = self.client.patch("/api/office-settings/", {"late_penalty_enabled": True}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(OfficeSettings.load().late_penalty_enabled)

    def test_duplicate_slot_updates_instead_of_creating_a_second_row(self):
        upsert_attendance(employee=self.staff, day=date(2026, 9, 1), actor=self.admin, check_in="09:00", check_out="17:00", allow_without_reason=True)
        upsert_attendance(employee=self.staff, day=date(2026, 9, 1), actor=self.admin, check_in="09:20", check_out="17:00", reason="Clock correction", allow_without_reason=False)
        self.assertEqual(AttendanceRecord.objects.filter(employee=self.staff, date=date(2026, 9, 1)).count(), 1)
        record = AttendanceRecord.objects.get(employee=self.staff, date=date(2026, 9, 1), shift_slot=1)
        self.assertEqual(record.status, "late")
        self.assertEqual(record.adjustments.count(), 1)

    def test_finalized_payroll_blocks_silent_attendance_and_adjustment_changes(self):
        upsert_attendance(employee=self.staff, day=date(2026, 9, 2), actor=self.admin, check_in="09:00", check_out="17:00", allow_without_reason=True)
        period = PayrollPeriod.objects.create(year=2026, month=9)
        calculate_period(period=period, actor=self.admin)
        approve_period(period=period, actor=self.admin)
        finalize_period(period=period, actor=self.admin)
        self.client.force_authenticate(self.admin)
        blocked = self.client.post("/api/attendance/mark/", {"employee_id": self.staff.id, "date": "2026-09-02", "check_in": "10:00", "check_out": "17:00", "reason": "Should not apply"}, format="json")
        self.assertEqual(blocked.status_code, 400)
        record = PayrollRecord.objects.get(period=period, employee=self.staff)
        adjust = self.client.post(f"/api/payroll/records/{record.id}/adjust/", {"kind": "deduction", "label": "Test", "amount": "5", "reason": "Nope"}, format="json")
        self.assertEqual(adjust.status_code, 400)

    def test_management_can_add_an_employee_but_cannot_change_policy_or_create_a_super_user(self):
        management = User.objects.create_user("lead2", password="Harbor@12345", role=User.Role.MANAGEMENT)
        self.client.force_authenticate(management)
        blocked = self.client.patch("/api/office-settings/", {"late_penalty_enabled": True}, format="json")
        self.assertEqual(blocked.status_code, 403)
        created = self.client.post("/api/employees/", {
            "first_name": "New", "last_name": "Hire", "joining_date": "2026-10-01",
            "employment_type": "full_time", "salary_type": "monthly", "basic_salary": "1500",
            "create_account": True, "account_username": "new.hire", "account_password": "Harbor@12345",
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(User.objects.get(username="new.hire").role, User.Role.EMPLOYEE)
        denied = self.client.post("/api/auth/users/", {
            "username": "another.lead", "password": "Harbor@12345", "role": "management",
        }, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_department_manager_does_not_receive_salary_fields(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(f"/api/employees/{self.staff.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("basic_salary", response.data)
        hidden = self.client.get(f"/api/employees/{self.other.id}/")
        self.assertEqual(hidden.status_code, 404)
