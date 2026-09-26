# syntax=docker/dockerfile:1.6
# Multi-stage build for the research-ai API (M36).

# ---------------------------------------------------------------------
# Stage 1 — builder
# ---------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml ./
COPY app ./app

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install .

# ---------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_ENV=production \
    LOG_FORMAT=json \
    DEBUG=false \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Install PostgreSQL client tools for backup/verify scripts.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        postgresql-client \
 && rm -rf /var/lib/apt/lists/*

# Non-root runtime user.
RUN groupadd --system --gid 1000 app \
 && useradd --system --uid 1000 --gid app --home /app app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app pyproject.toml ./

RUN mkdir -p /app/backups /app/storage \
 && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        r=urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=4); \
        sys.exit(0 if r.status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]