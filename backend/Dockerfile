# PurpleSol API (no computer-vision stack; see Dockerfile.worker).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY data ./data

RUN useradd --create-home --uid 10001 app && mkdir -p /app/storage && chown app /app/storage
USER app

ENV PORT=8000 APP_ENV=production
EXPOSE 8000
# Migrations run as Railway's pre-deploy command (python -m app.migrate).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
