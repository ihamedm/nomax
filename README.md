# NOMAX

Iranian local business & services marketplace (B2B2C), starting with Behbahan.

NOMAX is implemented through the v1 scope: OTP auth + RBAC, catalog and
PostGIS search, business onboarding, reviews, the anonymous quote flow,
notifications, permission-scoped admin, and Docker/production deploy.

- **User dashboard:** <http://localhost:8080/me> (Docker) or <http://localhost:5175/me> (Vite dev)
- **Account tabs:** home, my business, customers (incoming quote requests), quotes, and saved bookmarks.
- **Admin dashboard:** <http://localhost:8080/admin> (Docker) or <http://localhost:5175/admin> (Vite dev)
- **S3 file manager:** <http://localhost:8080/admin/files> (requires `storage.manage` and Arvan S3 credentials; files can be copied as public or temporary private links)
- **Theme:** light/dark switch in the app drawer (and admin header); the choice is saved locally.
- Current status and next phase: [`docs/roadmap-status.md`](docs/roadmap-status.md)
- Provider decisions: [`docs/adr/0001-provider-boundaries.md`](docs/adr/0001-provider-boundaries.md)
- Auth/RBAC decisions: [`docs/adr/0002-auth-rbac-dev-otp.md`](docs/adr/0002-auth-rbac-dev-otp.md)

## Stack

- **Backend:** FastAPI, async SQLAlchemy 2.0, PostgreSQL + PostGIS, Redis, Alembic
- **Frontend:** React 18, TypeScript, Vite, Tailwind, local Vazirmatn
- **SMS/OTP:** Mellipayamak shared-service pattern in production; console + admin
  dashboard in development
- **Storage:** ArvanCloud S3 (S3-compatible) in development and production; dashboard file manager
- **Push:** native Android via an Iranian provider; **no web push / VAPID**
- **Maps:** Iranian provider (Phase 2)
- **Jobs:** Redis + arq + Postgres outbox (Phase 5)

## Local setup

Requirements: Python 3.11+, Node 20+, Docker + Docker Compose.

```bash
# 1. Postgres (PostGIS) + Redis on 5433 / 6380
docker compose up -d

# Object storage uses ArvanCloud S3. Create `nomax-public` and `nomax-private`
# buckets, then put S3_ACCESS_KEY / S3_SECRET_KEY (and bucket names) from your
# ArvanCloud object-storage account in `.env`, and recreate the stack. Make the
# public bucket publicly readable or put a CDN in front of it (S3_PUBLIC_URL).
# Without credentials, local uploads fall back to the nomax_uploads volume and
# /ready reports storage as not_configured.

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

### Full Docker stack

```bash
docker compose up -d --build        # db, redis, api (:8002), worker, web (:8080)
docker compose ps                   # wait for api/db/redis to show (healthy)

# Bootstrap the first superadmin inside the API container
docker compose exec api python -m app.cli create-superadmin \
  --phone 09123456789 --name "Super Admin"
```

Then sign in at <http://localhost:8080/login> with that phone number. In local
development the OTP is shown on the login screen; a superadmin can also inspect
live codes at <http://localhost:8080/admin/dev-otps>.

### Dashboards

| Area | URL | Access |
| --- | --- | --- |
| App home | `/` | sticky header, hero search, 3-column categories, new/most-visited carousels, ad slots, mobile bottom nav |
| Dedicated search | `/search` | AJAX/debounced results, filters, map, trending searches (admin-managed) |
| User dashboard | `/me` | any signed-in user (profile, businesses, notifications with unread badges, analytics); owners also get `/me/reviews` for pending/private/approved reviews, owner moderation and replies |
| Admin dashboard | `/admin` | `admin` with assigned permissions, or `superadmin` |
| Admin users & permissions | `/admin/users` | superadmin only |
| Business management | `/admin/businesses` | `business.read` + create/update/delete/approve; filterable paginated table, details, add/edit/delete |
| Review moderation | `/admin/reviews` | `review.read` / `review.moderate`; all non-private reviews with business/status filters, search, pagination and approve/decline |
| Messages & announcements | `/admin/notifications` | `notification.manage`; in-app messages to all users, owners, customers or one receiver |
| Categories & subcategories | `/admin/categories` | `category.read` / `category.manage`; shared modular data table + CRUD |
| Tags | `/admin/tags` | `category.read` / `category.manage`; shared modular data table + CRUD |
| Banners & ads | `/admin/ads` | `ad.manage`; shared modular data table + CRUD |
| Content settings | `/admin/settings` | `admin.settings.manage`; trending search terms |
| All remaining models | `/admin/data` | superadmin only; generic paginated CRUD over remaining tables |
| Dev OTP viewer | `/admin/dev-otps` | superadmin, non-production only |

Every admin list is rendered through the shared
`frontend/src/features/admin/data-table.tsx` component, so density, pagination,
empty states and table layout changes apply to all lists at once. The dashboard
uses a compact scale (240px sidebar, 13px base type and 40px controls) so more
rows fit on laptop screens without affecting the customer-facing pages.

Auth-required actions and routes preserve where the user came from. Clicking
«ثبت نظر» while signed out opens a login prompt; `/login?next=…` returns to the
same business and reopens the review form automatically. The same mechanism
protects `/me/*`, `/admin/*`, quote pages, business creation/editing and saving
a business. Redirect targets are validated as same-origin paths.

A superadmin has unrestricted access to every module. To create a limited
admin, open `/admin/users`, click **«مدیر جدید»**, enter their phone number, then
select the permission codes for the modules they may access. Permissions are
enforced per endpoint with `require_permissions(...)`, and every role or
permission change is written to `admin_audit_logs`.

### Dev OTP flow

With `SMS_PROVIDER=console` (the default locally) OTPs are stored in Redis under
`dev:otp:{phone}` and the request response includes `dev_otp`. The login screen
auto-fills it, and a superadmin can inspect live codes at
`/admin/dev-otps` (API: `GET /api/v1/admin/dev/otps`).

Three guards keep this out of production:

1. the dev router is not mounted when `APP_ENV=production`;
2. `DEV_OTP_ENABLED` must be true;
3. the endpoint requires a superadmin token.

OTP request throttling is disabled in development by default
(`OTP_RATE_LIMIT_PER_HOUR=0` in `backend/.env.example` and
`docker-compose.yml`). Production keeps the built-in limit of 3 requests/hour;
set a positive value in `.env` to re-enable it locally.

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
| POST | `/api/v1/admin/users` | superadmin | create a new admin by phone (audited) |
| PATCH | `/api/v1/admin/users/{id}/role` | superadmin | change role (audited) |
| PATCH | `/api/v1/admin/users/{id}/permissions` | superadmin | set per-admin permissions (audited) |
| GET | `/api/v1/admin/dev/otps` | superadmin (non-production) | live dev OTPs |
| GET | `/api/v1/admin/dev/otps/{phone}` | superadmin (non-production) | one live dev OTP |

## Roles & permissions

- `customer` — default; can search, quote and review.
- `owner` — customer with at least one business.
- `admin` — accesses only the codes in `users.permissions`.
- `superadmin` — everything; can create admins and change roles/permissions.

Granular permissions only apply to the `admin` role; a demoted admin loses
access even if the permission list is still stored. Permission codes live in
`backend/app/core/permissions.py`. Unknown codes are rejected with 422, and
every admin creation, role change, and permission change writes an
`admin_audit_logs` row. A superadmin cannot demote themselves.

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
development: SMS uses the console provider and object storage uses ArvanCloud
S3. Fill `S3_ACCESS_KEY` and `S3_SECRET_KEY` in `.env`; `/ready` reports the
S3 connectivity state and the dashboard file manager (`/admin/files`) needs the
`storage.manage` permission. Without credentials, uploads fall back to local
disk for tests.

User business images are processed before storage: the browser optionally
downscales large photos, then the API applies EXIF orientation, an optional
filter, the requested crop/anchor, JPEG compression and named variants
(`square`, `card`, `wide`, `thumb`). Files are stored under
`uploads/businesses/{user_id}/{YYYY}/{MM}/` rather than the upload root. Admin
file-manager uploads are stored raw and are not processed.

> Never enable `DEV_OTP_ENABLED` in production. The router is still excluded by
> `APP_ENV`, but the flag is a second safety belt, not a feature toggle for prod.
