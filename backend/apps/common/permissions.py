from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.roles import ATTENDANCE, AUDIT, HR, PAYROLL_MANAGE, PAYROLL_VIEW, SUPER_ADMIN

PRIVILEGED = PAYROLL_VIEW | HR | ATTENDANCE


def role_of(user):
    return getattr(user, "role", "")


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and role_of(request.user) == SUPER_ADMIN


class IsHROrSuper(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and role_of(request.user) in HR


class CanManagePayroll(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and role_of(request.user) in PAYROLL_MANAGE


class CanViewPayroll(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and role_of(request.user) in PAYROLL_VIEW | {"employee"}


class OrgWriteOrAuthenticatedRead(BasePermission):
    """Any signed-in user can read organization reference data. HR and super admin can change it."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return role_of(request.user) in HR


class SettingsAccess(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return role_of(request.user) in AUDIT | ATTENDANCE
        return role_of(request.user) == SUPER_ADMIN
