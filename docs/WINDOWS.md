# Windows setup

## Prerequisites

- Python 3.12 or newer
- Node.js 20 or newer
- Docker Desktop, running before `docker compose up`

## Database

```powershell
cd "g:\All Tools Created\HRM"
docker compose up -d
docker ps
```

`hrm-postgres` should publish `0.0.0.0:5433`. Connection string:

```text
postgres://hrm:hrm_dev_password@127.0.0.1:5433/hrm
```

If port 5433 is busy, change the host port in `docker-compose.yml` and `DATABASE_URL` together.

## Backend

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

Put `SUPERUSER_USERNAME` and `SUPERUSER_PASSWORD` in the project `.env` first. `prepare_workspace` removes people, attendance, leave, and payroll, then creates that super user. Do not run `seed_demo` on a database you want to keep.

Refresh in-app alerts without opening the dashboard:

```powershell
.\.venv\Scripts\python.exe manage.py generate_alerts
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Vite listens on http://127.0.0.1:5173 and reads `VITE_API_URL` from the project `.env`. That value must end with `/api`.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py test apps.attendance apps.payroll apps.accounts
```

## Start over

This deletes people, attendance, leave, and payroll, then recreates the super user from the project `.env`:

```powershell
.\.venv\Scripts\python.exe manage.py prepare_workspace
```

Do not run `seed_demo --reset` against a database that holds real office records. That command loads the old sample company.

## Media and logs

Uploaded photos and leave documents go to `backend/media/`. Application errors are written to `backend/logs/hrm.log`.
