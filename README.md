# NOMAX

Iranian local business & services marketplace (B2B2C), starting with Behbahan.

Phase 0 (foundations, design system, catalog seed) and Phase 1 (OTP auth, RBAC,
admin shell, dev OTP) are implemented. The app is a working walking skeleton:
**dev OTP login → categorized home grid → admin panel**.

- Current status and next phase: [`docs/roadmap-status.md`](docs/roadmap-status.md)
- Provider decisions: [`docs/adr/0001-provider-boundaries.md`](docs/adr/0001-provider-boundaries.md)
- Auth/RBAC decisions: [`docs/adr/0002-auth-rbac-dev-otp.md`](docs/adr/0002-auth-rbac-dev-otp.md)

## Stack

- **Backend:** FastAPI, async SQLAlchemy 2.0, PostgreSQL + PostGIS, Redis, Alembic
- **Frontend:** React 18, TypeScript, Vite, Tailwind, local Vazirmatn
- **SMS/OTP:** Mellipayamak shared-service pattern in production; console + admin
  dashboard in development
- **Storage:** ArvanCloud S3 in production, MinIO locally (Phase 3)
- **Push:** native Android via an Iranian provider; **no web push / VAPID**
- **Maps:** Iranian provider (Phase 2)
- **Jobs:** Redis + arq + Postgres outbox (Phase 5)

## Local setup

Requirements: Python 3.11+, Node 20+, Docker + Docker Compose.

```bash
# 1. Postgres (PostGIS) + Redis on 5433 / 6380
docker compose up -d

# Optional object storage (MinIO). Needs an accessible registry image:
#   MINIO_IMAGE=docker.arvancloud.ir/minio/minio:... docker compose --profile storage up -d
# The API does not need MinIO until Phase 3 uploads.

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# 3. Schema + catalog (idempotent)
alembic upgrade head
python3 -m app.cli seed-categories

# 4. Bootstrap the first superadmin
python3 -m app.cli create-superadmin --phone 09123456789 --name "Super Admin"

# 5. Run the API
python3 -m uvicorn app.main:app --reload --port 8001
```

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env   # optional; the Vite proxy works with empty values
npm run dev            # http://localhost:5175
```

API docs: <http://localhost:8001/docs>
Readiness: <http://localhost:8001/ready> (checks Postgres + Redis)

### Dev OTP flow

With `SMS_PROVIDER=console` (the default locally) OTPs are stored in Redis under
`dev:otp:{phone}` and the request response includes `dev_otp`. The login screen
auto-fills it, and a superadmin can inspect live codes at
`/admin/dev-otps` (API: `GET /api/v1/admin/dev/otps`).

Three guards keep this out of production:

1. the dev router is not mounted when `APP_ENV=production`;
2. `DEV_OTP_ENABLED` must be true;
3. the endpoint requires a superadmin token.

### Forgot the seeded categories?

```bash
python3 -m app.cli seed-categories
```

The tree lives in `backend/app/db/seed_data/categories.json` — 18 categories and
188 subcategories extracted from the official NOMAX design, including the
standard service tags used later by search.

## Phase 0/1 API

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | public | liveness |
| GET | `/ready` | public | readiness (DB + Redis, 503 when degraded) |
| GET | `/api/v1/categories` | public | 18 categories with subcategory counts |
| GET | `/api/v1/categories/{id}/subcategories` | public | subcategories + standard tags |
| POST | `/api/v1/auth/otp/request` | public | send (or, in dev, return) an OTP |
| POST | `/api/v1/auth/otp/verify` | public | exchange OTP for access + refresh tokens |
| POST | `/api/v1/auth/refresh` | public | rotate refresh token (reuse revokes the family) |
| POST | `/api/v1/auth/logout` | public | revoke the refresh family |
| GET | `/api/v1/auth/me` | user | current profile |
| GET | `/api/v1/admin/me` | user | admin shell identity + `is_superadmin` |
| GET | `/api/v1/admin/permissions` | superadmin | permission catalog |
| GET | `/api/v1/admin/users` | superadmin | active users |
| PATCH | `/api/v1/admin/users/{id}/role` | superadmin | change role (audited) |
| PATCH | `/api/v1/admin/users/{id}/permissions` | superadmin | set per-admin permissions (audited) |
| GET | `/api/v1/admin/dev/otps` | superadmin (non-production) | live dev OTPs |
| GET | `/api/v1/admin/dev/otps/{phone}` | superadmin (non-production) | one live dev OTP |

## Roles & permissions

- `customer` — default; can search, quote and review.
- `owner` — customer with at least one business (Phase 3).
- `admin` — accesses only the codes in `users.permissions`.
- `superadmin` — everything; only superadmin can change roles/permissions.

Granular permissions only apply to the `admin` role; a demoted admin loses
access even if the permission list is still stored. Permission codes live in
`backend/app/core/permissions.py`. Unknown codes are rejected with 422, and
every role/permission change writes an `admin_audit_logs` row. A superadmin
cannot demote themselves.

## Health and operations

- `/health` — process liveness.
- `/ready` — `SELECT 1` + `redis.ping()`; returns `503` with per-dependency
  `checks` when something is down.
- `sms_logs` records every provider attempt (`sent` / `failed`).
- `admin_audit_logs` records role/permission changes.

## Tests

```bash
cd backend
python3 -m pytest -q --timeout=30     # 44 tests, SQLite + in-memory Redis
```

The frontend gate is:

```bash
cd frontend
npm run build                          # tsc --noEmit + vite build
```

Tests use a temporary SQLite database and an in-memory Redis fake, so no
services are needed. CI runs the backend suite
(`.github/workflows/backend.yml`).

## Layout

```
backend/
  app/
    api/v1/      auth, categories, admin, health routers
    core/        config, security, deps, permissions, redis
    db/          Base, session, seed + seed_data/categories.json
    models/      User, AuditLog, Category, Subcategory, SmsLog
    schemas/     request/response models
    services/    auth, OTP, SMS provider
    cli.py       create-superadmin, seed-categories
  alembic/       migrations 0001–0002
  tests/
frontend/
  src/
    app/         App, router, error boundary
    components/  ui primitives (button, input, badge, bottom sheet, toast)
    features/    auth, home, admin
    lib/         api client, tokens, digits, Jalali, format
    stores/      auth store
  public/fonts/  Vazirmatn woff2 + OFL license
docs/
  adr/           provider and auth decisions
  roadmap-status.md
docker-compose.yml
.github/workflows/backend.yml
```

## Environment

Backend variables are documented in `backend/.env.example`; frontend variables
in `frontend/.env.example`. Nothing calls a foreign runtime service in
development: SMS uses the console provider and storage is optional.

> Never enable `DEV_OTP_ENABLED` in production. The router is still excluded by
> `APP_ENV`, but the flag is a second safety belt, not a feature toggle for prod.
