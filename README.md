# NOMAX

Iranian local business & services marketplace (B2B2C), starting with Behbahan.

Phase 1 (auth, OTP, RBAC, admin shell, dev OTP) is implemented in `backend/`.
Frontend (React + Tailwind + shadcn, Capacitor wrapper) comes next.

## Stack

- **Backend:** FastAPI, async SQLAlchemy 2.0, PostgreSQL + PostGIS, Redis, Alembic
- **Frontend:** React 18 + TypeScript + Tailwind + shadcn/ui (planned)
- **SMS/OTP:** Mellipayamak in production; console + admin dashboard in dev
- **Storage:** ArvanCloud S3 in production, MinIO locally
- **Push:** Najva (native Android via Capacitor), no web push
- **Maps:** Neshan (Phase 2)
- **Jobs:** Redis + arq with a Postgres outbox (Phase 5)

## Local setup

Requirements: Python 3.11+, Docker + Docker Compose.

```bash
# 1. Postgres (PostGIS) + Redis on 5433 / 6380
docker compose up -d

# 2. Backend dependencies
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Configuration
cp .env.example .env

# 4. Schema
alembic upgrade head

# 5. Bootstrap the first superadmin
python3 -m app.cli create-superadmin --phone 09123456789 --name "Super Admin"

# 6. Run
python3 -m uvicorn app.main:app --reload --port 8001
```

API docs: <http://localhost:8001/docs>

## Phase 1 API

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | public | liveness |
| POST | `/api/v1/auth/otp/request` | public | send (or, in dev, return) an OTP |
| POST | `/api/v1/auth/otp/verify` | public | exchange OTP for access + refresh tokens |
| POST | `/api/v1/auth/refresh` | public | rotate refresh token (reuse revokes the family) |
| POST | `/api/v1/auth/logout` | public | revoke the refresh family |
| GET | `/api/v1/auth/me` | user | current profile |
| GET | `/api/v1/admin/me` | user | admin shell identity + `is_superadmin` |
| GET | `/api/v1/admin/users` | superadmin | list users |
| PATCH | `/api/v1/admin/users/{id}/role` | superadmin | change role (audited) |
| PATCH | `/api/v1/admin/users/{id}/permissions` | superadmin | set per-admin permissions (audited) |
| GET | `/api/v1/admin/dev/otps` | superadmin (non-production) | live dev OTPs |
| GET | `/api/v1/admin/dev/otps/{phone}` | superadmin (non-production) | one live dev OTP |

### Dev OTP flow

With `SMS_PROVIDER=console` (or `APP_ENV=local`), OTPs are stored in Redis under
`dev:otp:{phone}` and the request response includes `dev_otp`. The admin
dashboard reads them from `/api/v1/admin/dev/otps` and shows the code to the
operator. The dev router is not mounted when `APP_ENV=production` and is also
gated by a superadmin dependency.

> The dev router is hidden in production **and** requires a superadmin token.
> Never enable `DEV_OTP_ENABLED` in a production environment.

## Roles & permissions

- `customer` — default; becomes `owner` after adding a business (Phase 2).
- `owner` — customer with at least one business.
- `admin` — accesses only the permissions listed in `users.permissions`.
- `superadmin` — everything; only superadmin can change roles/permissions.

Permission codes live in `backend/app/core/permissions.py`
(`ADMIN_PERMISSION_CATALOG`). Unknown codes are rejected with 422, and every
role/permission change writes an `admin_audit_logs` row.

## Tests

```bash
cd backend
python3 -m pytest -q --timeout=30
```

Tests use a temporary SQLite database and an in-memory Redis fake, so no
services are needed. CI runs the same command (`.github/workflows/backend.yml`).

## Layout

```
backend/
  app/
    api/v1/      auth, admin, health routers
    core/        config, security, deps, permissions, redis
    db/          Base + async session
    models/      User, AuditLog
    schemas/     request/response models
    services/    auth, OTP, SMS provider
    cli.py       operator commands
  alembic/       migrations
  tests/
docker-compose.yml
.github/workflows/backend.yml
proposal.md
```
