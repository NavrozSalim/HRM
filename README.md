# Wesolucions HRM

Wesolucions HRM is an office human-resource system for employees, attendance, leave, payroll, and monthly history. The React app and the Django API live in separate directories and share one PostgreSQL database.

Salary and attendance math runs on the backend. Dashboard figures are counted from stored records.

## What needs something outside this app

- **Biometric devices are not connected.** `GET /api/attendance/biometric/` reports `connected: false`. If `biometric_enabled` is off, a punch is rejected and nothing is stored. If it is on and no adapter is installed, the API returns 501. Turning the setting on does not pretend a reader is attached.
- **Email and SMS are not sent.** Notices stay in the in-app inbox.
- **PostgreSQL is required** for the normal setup. SQLite is only a local fallback when `USE_SQLITE=True`.

## Layout

- `backend/` — Django 5 and Django REST Framework
- `frontend/` — React 18, Vite, Tailwind CSS
- `docker-compose.yml` — local PostgreSQL 16 on host port **5433**
- `docker-compose.prod.yml` — production database, API, and web server
- `docs/` — deployment, backup, and API notes

## Windows development

1. Install Python 3.12+, Node.js 20+, and Docker Desktop.
2. Start the database:

```powershell
cd "g:\All Tools Created\HRM"
docker compose up -d
```

The database user is `hrm`, the password is `hrm_dev_password`, and the database name is `hrm`. Port 5433 avoids a local PostgreSQL install that may already be using 5432.

3. Backend:

```powershell
cd "g:\All Tools Created\HRM"
copy .env.example .env
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py prepare_workspace
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Set `SUPERUSER_USERNAME` and `SUPERUSER_PASSWORD` in the project `.env` before `prepare_workspace`. That command clears people, attendance, leave, and payroll, then creates the super user from those values. Do not run `seed_demo` unless you want the old sample company back.

4. Frontend, in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The API is http://127.0.0.1:8000/api and the interactive schema is http://127.0.0.1:8000/api/docs/.

## Deployment

On a server, set `SECRET_KEY`, `PUBLIC_HOST`, and `POSTGRES_PASSWORD` in the project `.env`, then run:

```powershell
docker compose -f docker-compose.prod.yml up -d --build
```

That stack migrates the database and creates the super user only when the account is missing. It does not load sample data. The full checklist is in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Accounts

Sign-in is username and password only.

| Role | Created by | What they do |
| --- | --- | --- |
| Super user | `SUPERUSER_USERNAME` and `SUPERUSER_PASSWORD` in the project `.env` | Creates management and employee users, and can change company rules |
| Management | Super user, from Organization → Users | Adds employees (with a login), attendance, leave, and payroll |
| Employee | Super user or management, from Add employee → Create login | Checks in, requests leave, and views their own attendance and salary |

## Tests

From `backend`:

```powershell
.\.venv\Scripts\python.exe manage.py test apps.attendance apps.payroll apps.accounts
```

Attendance tests cover grace, overnight shifts, incomplete punches, and weekly offs. Payroll tests cover full-month pay, holidays, unpaid leave, optional absence and late penalties, mid-month joining, a fixed divisor, and daily wages.

## Roles

Permissions are enforced on the API.

- **Super admin** — users, policy, employees, attendance, leave, payroll, reports.
- **HR manager** — employees, attendance, leave, and reports. Can view payroll, not finalize or pay it.
- **Accountant** — payroll, payments, and payroll audit entries. Cannot change office policy.
- **Department manager** — own department only. Can review attendance and leave. Cannot see salaries.
- **Employee** — own profile, attendance, leave, and salary slips. Cannot open anyone else's pay.

Approved leave, weekly offs, and public holidays are not unauthorized absences. Weekly offs and public holidays are not deducted from a monthly salary by default. Late penalties and absence deductions stay at zero until a super admin enables them in Organization. A finalized payroll month cannot be edited until it is reopened with a reason.

## More documentation

- [Windows notes and day-to-day commands](docs/WINDOWS.md)
- [Production deployment](docs/DEPLOYMENT.md)
- [Backup and recovery](docs/BACKUP.md)
- [API overview](docs/API.md)
