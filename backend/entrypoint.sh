#!/bin/sh
set -eu
mkdir -p /app/media /app/staticfiles /app/logs
chown -R hrm:hrm /app/media /app/staticfiles /app/logs
su -s /bin/sh hrm -c "python manage.py migrate --noinput"
su -s /bin/sh hrm -c "python manage.py collectstatic --noinput"
su -s /bin/sh hrm -c "python manage.py ensure_superuser"
exec setpriv --reuid=hrm --regid=hrm --init-groups \
  gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
