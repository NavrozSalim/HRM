# API overview

Base URL in development: `http://127.0.0.1:8000/api`

Interactive schema: `http://127.0.0.1:8000/api/docs/`

Send `Authorization: Bearer <access>` on every route except login, refresh, company name, and health. Access tokens last 30 minutes. Refresh tokens last 7 days, rotate, and are blacklisted on logout.

Money is decimal text. Dates are `YYYY-MM-DD`. Weekdays are Monday `0` through Sunday `6`.

## Authentication

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/login/` | Username and password. Returns `access`, `refresh`, and `user`. |
| POST | `/auth/refresh/` | Rotates the refresh token. |
| POST | `/auth/logout/` | Blacklists the refresh token. |
| GET | `/auth/me/` | Current user and capabilities. |
| POST | `/auth/change-password/` | `old_password`, `new_password`. |
| GET | `/auth/company/` | Public company name for the sign-in screen. |
| GET/POST | `/auth/users/` | Super admin account management. |

## Organization

Authenticated users can read locations, departments, job titles, shifts, and holidays. HR and super admin can change them. Office policy is readable by managers and writable only by a super admin: `GET` and `PATCH /office-settings/`.

## Employees

| Method | Path | Purpose |
| --- | --- | --- |
| GET/POST | `/employees/` | Directory. Salary and bank fields are omitted when the caller cannot see pay. |
| GET/PATCH | `/employees/{id}/` | Profile. Hard delete is rejected. |
| POST | `/employees/{id}/deactivate/` | Sets an exit date and keeps payroll history. |
| POST | `/employees/{id}/reactivate/` | Returns an employee to active. |
| GET | `/employees/{id}/timeline/` | Employment status history. |
| GET/POST | `/allowances/` | Recurring allowances. Writes mark the open payroll month stale. |

## Attendance

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/attendance/daily/?date=` | One office day. |
| GET | `/attendance/grid/?year=&month=` | Monthly grid. |
| POST | `/attendance/mark/` | Manual mark or correction. A change needs a reason. |
| POST | `/attendance/bulk/` | Mark many employees for one date. |
| POST | `/attendance/check-in/` | Employee self check-in when the office setting is on. |
| POST | `/attendance/check-out/` | Employee self check-out. |
| POST | `/attendance/import/` | `.xlsx` upload. HR or super admin. |
| POST | `/attendance/close-day/` | Materialize past unmarked days. |
| GET | `/attendance/punctuality/?year=&month=` | Late, absence, and overtime totals. |
| GET | `/attendance/records/` | Filterable history. |
| GET/POST | `/attendance/biometric/` | Integration point. Not connected to a device. |

One employee, date, and shift slot has one row. Lateness uses the snapshotted shift and grace period. A finalized payroll month blocks attendance edits until payroll is reopened.

## Leave

| Method | Path | Purpose |
| --- | --- | --- |
| GET/POST | `/leave-types/` | Casual, sick, annual, unpaid, emergency, or a custom type. |
| GET | `/leave-balances/?employee=` | Entitled, used, pending, available. |
| POST | `/leave-balances/{id}/adjust/` | HR balance correction with a reason. |
| GET/POST | `/leave-requests/` | Employees can only file their own request. |
| POST | `/leave-requests/{id}/approve/` | Approves and writes attendance. |
| POST | `/leave-requests/{id}/reject/` | Rejection with a note. |
| POST | `/leave-requests/{id}/cancel/` | Returns reserved balance. |
| GET | `/leave-calendar/?year=&month=` | Month view. |

Overlapping requests are rejected. Approved paid leave is not an unauthorized absence.

## Payroll

All amounts are calculated in `apps/payroll/engine.py` and stored by `apps/payroll/services.py`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET/POST | `/payroll/periods/` | Open a month. |
| POST | `/payroll/periods/{id}/calculate/` | Rebuilds lines. Manual adjustments remain. |
| POST | `/payroll/periods/{id}/approve/` | Marks the preview approved. |
| POST | `/payroll/periods/{id}/finalize/` | Locks the month inside a transaction and recovers advances. |
| POST | `/payroll/periods/{id}/reopen/` | Requires `reason` and reverses advance recovery. |
| GET | `/payroll/records/?period=` | Snapshot used by slips and reports. |
| POST | `/payroll/records/{id}/adjust/` | Manual earning or deduction with a reason. |
| POST | `/payroll/records/{id}/pay/` | Payment after finalization. Cannot exceed net. |
| GET | `/payroll/records/{id}/slip/?format=pdf` | Salary slip. |
| POST | `/payroll/bonuses/` | Bonus for a year and month. |
| POST | `/payroll/deductions/` | Approved deduction. |
| POST | `/payroll/advances/` | Advance. Remaining balance starts equal to the amount. |

Department managers receive an empty payroll list. Employees receive only their own records. HR can view a period and cannot calculate, approve, finalize, adjust, or pay it.

Gross pay is basic plus allowances, bonuses, and overtime. Net pay subtracts approved deductions, unpaid leave, advances, and any attendance penalty that is explicitly enabled. A complete monthly salary is not divided by 30. The divisor is used for the day rate and for someone who joins or leaves mid-month.

## Reports, search, and files

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/dashboard/?date=&department=` | Live counts for the signed-in scope. |
| GET | `/reports/employee-monthly/?employee=&year=&month=` | One person. Add `format=pdf` or `xlsx`. |
| GET | `/reports/company-monthly/?year=&month=` | Office comparison. |
| GET | `/exports/{kind}/?format=xlsx` | `employees`, `attendance`, `attendance-template`, `leave`, `payroll`. Filters and permissions apply. |
| GET | `/search/?q=` | Names, codes, emails, and leave reasons. No salary or bank data. |
| GET | `/audit-logs/` | HR and super admin see the log. Accountants see payroll entries. |
| GET | `/notifications/` | Inbox plus an `unread` count. |
| POST | `/notifications/read/` | `{ "ids": [1] }` or `{ "all": true }`. |
| POST | `/notifications/generate/` | HR rebuilds late, missing checkout, leave, payroll, and birthday notices. |
| GET | `/health/` | `{ "status": "ok" }` without a token. |

Exports and reports refuse records the caller is not allowed to see. Passwords, tokens, and full bank account numbers are not written to the audit log.
