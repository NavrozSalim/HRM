# Database backup and recovery

Payroll and attendance history live in PostgreSQL. Back up that database, plus `backend/media/` for photos and leave documents. A backup of the code does not contain employee records.

## Docker development database

The compose service is `hrm-postgres` and the data volume is `hrm_pgdata`.

Create a custom-format dump:

```powershell
docker exec hrm-postgres pg_dump -U hrm -d hrm -Fc -f /tmp/hrm.dump
docker cp hrm-postgres:/tmp/hrm.dump .\hrm.dump
```

Restore into an empty database. This replaces objects in `hrm`:

```powershell
docker cp .\hrm.dump hrm-postgres:/tmp/hrm.dump
docker exec hrm-postgres pg_restore -U hrm -d hrm --clean --if-exists /tmp/hrm.dump
```

If the container was removed but the volume remains, `docker compose up -d` brings the same data back. `docker compose down -v` deletes the volume and the data with it.

Copy `backend/media` alongside the dump:

```powershell
Compress-Archive -Path .\backend\media -DestinationPath .\hrm-media.zip
```

## Production

Run a daily dump from the database host and copy it off the server:

```bash
pg_dump -U hrm -d hrm -Fc -f /var/backups/hrm-$(date +%F).dump
```

Keep at least one copy on another disk or object store. Test a restore on a spare database before you need it.

Restore:

```bash
createdb -U postgres hrm_restore
pg_restore -U hrm -d hrm_restore /var/backups/hrm-YYYY-MM-DD.dump
```

Point a spare `.env` at `hrm_restore`, run the API, and confirm a known employee, a finalized payroll month, and a salary slip before you replace the live database.

To replace production:

1. Stop Gunicorn so nobody writes during the restore.
2. Restore the dump into `hrm`, or rename databases and point `DATABASE_URL` at the restored one.
3. Restore `media/` from the same backup window.
4. Start Gunicorn and sign in as a super admin.
5. Open one finalized month and confirm it still matches the slip you checked before the outage.

Do not run `seed_demo --reset` as a recovery step. It deletes office data and inserts the synthetic demo company.

## What a backup does not include

- `.env` secrets. Store those in your password manager.
- JSON web tokens. Users sign in again after a restore.
- A biometric reader. This application does not store device credentials because no reader is connected.
