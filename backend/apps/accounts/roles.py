"""Role groups used by permissions.

The app offers three roles: super user, management, and employee.
Older role values stay in the groups so existing tests keep their meaning.
"""

SUPER_ADMIN = "super_admin"
MANAGEMENT = "management"
EMPLOYEE = "employee"

# Sees every employee and company salary figures.
OFFICE = {SUPER_ADMIN, MANAGEMENT, "hr_manager", "accountant"}
# Can add and edit employees, including employee logins.
HR = {SUPER_ADMIN, MANAGEMENT, "hr_manager"}
# Can see salary figures.
PAYROLL_VIEW = {SUPER_ADMIN, MANAGEMENT, "hr_manager", "accountant"}
# Can calculate, approve, finalize, and pay salaries.
PAYROLL_MANAGE = {SUPER_ADMIN, MANAGEMENT, "accountant"}
# Can mark attendance and decide leave.
ATTENDANCE = {SUPER_ADMIN, MANAGEMENT, "hr_manager", "department_manager"}
AUDIT = {SUPER_ADMIN, MANAGEMENT, "hr_manager", "accountant"}
