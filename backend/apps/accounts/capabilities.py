from apps.accounts.roles import ATTENDANCE, AUDIT, HR, MANAGEMENT, PAYROLL_MANAGE, PAYROLL_VIEW, SUPER_ADMIN
from apps.organization.models import OfficeSettings


def capabilities_for(user):
    role = getattr(user, "role", "")
    profile = getattr(user, "employee_profile", None)
    try:
        checkin = OfficeSettings.load().self_checkin_enabled and profile is not None
    except Exception:
        checkin = False
    return {
        "manage_users": role == SUPER_ADMIN,
        "manage_settings": role == SUPER_ADMIN,
        "manage_org": role in HR,
        "manage_employees": role in HR,
        "manage_attendance": role in ATTENDANCE,
        "manage_leave": role in ATTENDANCE,
        "approve_leave": role in ATTENDANCE,
        "view_payroll": role in PAYROLL_VIEW,
        "manage_payroll": role in PAYROLL_MANAGE,
        "view_audit": role in AUDIT,
        "can_check_in": checkin,
        "view_own_salary": role in PAYROLL_VIEW or role == "employee" or role == MANAGEMENT,
    }
