# Production deployment

The production stack is PostgreSQL, Gunicorn, and Nginx. It is defined in `docker-compose.prod.yml`. Local development still uses `docker-compose.yml`, which starts only the database on port 5433.

The container start-up runs migrations, collects static files, and creates the super user from `SUPERUSER_USERNAME` and `SUPERUSER_PASSWORD` when that account does not exist. It does not change an existing password and it does not delete office data. Do not run `prepare_workspace` or `seed_demo` on a production database.

## Before the first start

Edit the project `.env`:

```text
SECRET_KEY=<a unique string of at least 40 characters>
SUPERUSER_USERNAME=admin
SUPERUSER_PASSWORD=<at least 8 characters>
POSTGRES_DB=hrm
POSTGRES_USER=hrm
POSTGRES_PASSWORD=<database password>
PUBLIC_HOST=hrm.wesolucions.com
PUBLIC_API_URL=/api
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://hrm.wesolucions.com
```

`SECRET_KEY` cannot be one of the sample values from `.env.example`. `PUBLIC_HOST` is the name or IP people type in the browser. `POSTGRES_PASSWORD` must not contain `@`, `:`, `/`, `#`, or spaces. `DEBUG` can stay `True` in the file for local development; the production compose file forces it off and points the API at the database container.

`PUBLIC_API_URL=/api` keeps the browser on the same site as the API, so the frontend image does not have to be rebuilt when the host name changes.

## Start

From the project folder:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Open `https://hrm.wesolucions.com/`. Sign in with `SUPERUSER_USERNAME` and `SUPERUSER_PASSWORD`. The first boot creates that account. Later boots leave the password as it is, including a password changed inside the app.

`GET /api/health/` returns `{"status": "ok"}` when the API can reach the database. `/api/docs/` is not published by the production stack.

## What the stack serves

- `/` — the React app, with unknown paths returned to `index.html`
- `/api/` — Gunicorn
- `/admin/` — Django admin
- `/static/` — collected admin files
- `/media/` — uploaded photos and leave files

Uploaded files live in the `hrm_prod_media` volume. Database files live in `hrm_prod_pgdata`.

## Domain

In the DNS settings for `wesolucions.com`, add a record and leave the root domain as it is:

| Type | Name | Value |
| --- | --- | --- |
| A | hrm | 158.220.105.10 |

`HRM.wesolucions.com` and `hrm.wesolucions.com` are the same name. Wait until that record answers with `158.220.105.10` before starting the stack. Caddy then requests a certificate and serves `https://hrm.wesolucions.com`. Ports 80 and 443 on the server must be open. Port 80 is only used to prove control of the domain and to send browsers to HTTPS.

## After go-live

- Change the super-user password under My account. The container will not overwrite it.
- Set the company time zone, currency, weekly offs, grace period, and salary divisor in Organization.
- Leave late penalties and absence deductions off until the office writes the policy down and a super user enables it.
- Confirm biometric stays disconnected until a real adapter is installed.

Backups are described in [BACKUP.md](BACKUP.md).
