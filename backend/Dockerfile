FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

COPY pyproject.toml ./

# psql/pg_dump power the superadmin database backup dashboard. Keep this
# layer before the source copy so normal code changes don't reinstall it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN --mount=type=cache,target=/root/.cache/pip pip install .

EXPOSE 8001

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8001"]
