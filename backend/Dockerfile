FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 util-linux login \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 hrm

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/media /app/staticfiles /app/logs \
    && chown -R hrm:hrm /app \
    && chmod 755 /app/entrypoint.sh

EXPOSE 8000

CMD ["sh", "/app/entrypoint.sh"]
