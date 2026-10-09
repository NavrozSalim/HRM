import re
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.attendance.models import AttendanceAdjustment, AttendanceRecord
from apps.common.models import AuditLog
from apps.employees.models import Employee, EmployeeAllowance, EmploymentEvent
from apps.leaves.models import LeaveBalance, LeaveRequest, LeaveType
from apps.notifications.models import Notification
from apps.organization.models import Department, Holiday, JobTitle, OfficeLocation, Shift
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

User = get_user_model()


class Command(BaseCommand):
    help = "Remove demo records and make sure the super user from the environment exists."

    def handle(self, *args, **options):
        username, password, wrote_env = self._credentials()
        with transaction.atomic():
            self._clear_demo_data()
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": settings.SUPERUSER_EMAIL or "",
                    "first_name": settings.SUPERUSER_FIRST_NAME or "",
                    "last_name": settings.SUPERUSER_LAST_NAME or "",
                    "role": User.Role.SUPER_ADMIN,
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            user.email = settings.SUPERUSER_EMAIL or user.email
            user.first_name = settings.SUPERUSER_FIRST_NAME or user.first_name
            user.last_name = settings.SUPERUSER_LAST_NAME or user.last_name
            user.role = User.Role.SUPER_ADMIN
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.set_password(password)
            user.save()
        state = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Database is ready. Demo records are gone. Super user '{username}' was {state}."))
        if wrote_env:
            self.stdout.write("SUPERUSER_USERNAME and SUPERUSER_PASSWORD were empty, so values were saved in the project .env.")

    def _credentials(self):
        username = (settings.SUPERUSER_USERNAME or "").strip()
        password = settings.SUPERUSER_PASSWORD or ""
        wrote = False
        if not username:
            username = "admin"
            wrote = True
        if not password:
            password = secrets.token_urlsafe(12)
            wrote = True
        if wrote:
            self._write_env(username, password)
        if len(password) < 8:
            raise CommandError("SUPERUSER_PASSWORD must be at least 8 characters.")
        return username, password, wrote

    def _write_env(self, username, password):
        path = settings.ENV_FILE
        text = path.read_text(encoding="utf-8") if path.exists() else ""

        def put(key, value):
            nonlocal text
            line = f"{key}={value}"
            if re.search(rf"^{re.escape(key)}=", text, re.M):
                text = re.sub(rf"^{re.escape(key)}=.*$", line, text, count=1, flags=re.M)
            else:
                if text and not text.endswith("\n"):
                    text += "\n"
                text += line + "\n"

        put("SUPERUSER_USERNAME", username)
        put("SUPERUSER_PASSWORD", password)
        put("SUPERUSER_EMAIL", settings.SUPERUSER_EMAIL or "")
        put("SUPERUSER_FIRST_NAME", settings.SUPERUSER_FIRST_NAME or "")
        put("SUPERUSER_LAST_NAME", settings.SUPERUSER_LAST_NAME or "")
        path.write_text(text, encoding="utf-8")

    def _clear_demo_data(self):
        for model in (
            AdvanceRecovery,
            SalaryPayment,
            PayrollLineItem,
            Bonus,
            Deduction,
            SalaryAdvance,
            PayrollRecord,
            PayrollPeriod,
            AttendanceAdjustment,
            AttendanceRecord,
            LeaveRequest,
            LeaveBalance,
            EmployeeAllowance,
            EmploymentEvent,
            Employee,
            Notification,
            AuditLog,
            JobTitle,
            Department,
            Shift,
            Holiday,
            LeaveType,
            OfficeLocation,
        ):
            model.objects.all().delete()
        BlacklistedToken.objects.all().delete()
        OutstandingToken.objects.all().delete()
        User.objects.all().delete()
