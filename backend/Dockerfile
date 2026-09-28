# Backend container (Step 16) — static configuration, NOT runtime-verified
# in this environment (Docker unavailable). No secrets are baked in: all
# configuration arrives via environment variables / mounted .env at runtime.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (layer-cached), with verified constraints.
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Application code.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Non-root runtime user; uploads live on a mounted volume.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Start API + run migrations first (bounded, no auto-downloads).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
