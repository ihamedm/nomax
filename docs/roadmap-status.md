# NOMAX roadmap status

Last updated: 2026-10-26

This file is the hand-off point between agent sessions. Update it at the end of
every working session so the next agent knows what actually runs.

## Phase 0 — Foundations

| Item | Status | Notes |
|---|---|---|
| Compose: Postgres/PostGIS + Redis | ✅ | `docker compose up -d`; ports 5433 / 6380 |
| Compose: MinIO + bucket init | ⚠️ opt-in | `--profile storage`; image must come from an accessible registry (see ADR 0001) |
| Alembic baseline + 0002 catalog/sms | ✅ | `alembic upgrade head` |
| Response envelope + `/health` + `/ready` | ✅ | `/ready` checks DB and Redis, returns 503 when degraded |
| Provider boundaries + ADRs | ✅ | `docs/adr/0001-provider-boundaries.md` |
| Tailwind, RTL, BottomSheet, Toasts | ✅ | `components/ui/*` |
| Local Vazirmatn + OFL license | ✅ | `public/fonts/*`, preload in `index.html` |
| Persian digit + Jalali utilities | ✅ | `lib/digits.ts`, `lib/jalali.ts` |
| 18 categories / 188 subcategories seed | ✅ | extracted from the official design; `python -m app.cli seed-categories` |
| Seeded categories render | ✅ | home grid + subcategory bottom sheet |

## Phase 1 — Auth, OTP, RBAC, admin shell

| Item | Status | Notes |
|---|---|---|
| OTP request/verify + rate limit + attempts | ✅ | HMAC hash in prod, dev mirror in Redis |
| Refresh rotation + replay revocation + logout | ✅ | single-flight refresh on the client |
| National ID validation + uniqueness | ✅ | checksum validator in `core/security.py` |
| RBAC catalog + `require_permissions` | ✅ | granular list only for `admin` |
| Superadmin CLI | ✅ | `python -m app.cli create-superadmin` |
| Audit log on role/permission changes | ✅ | `admin_audit_logs` |
| Dev OTP endpoints, triple guarded | ✅ | router not mounted in production |
| Mellipayamak pattern provider + retry + `sms_logs` | ✅ | credentials/KYC still external |
| Admin shell: overview, users/permissions, dev OTPs | ✅ | `/admin`, `/admin/users`, `/admin/dev-otps` |
| Frontend entrypoint/router/error boundary | ✅ | `src/main.tsx`, `src/app/*` |

**Verification (2026-10-26):**

- `cd backend && python3 -m pytest -q` → 44 passing.
- `cd frontend && npm run build` → typecheck + production build passing.
- Browser E2E at 430px (headless Chrome through the Vite proxy): home renders 18
  categories with no horizontal overflow; the category bottom sheet lists
  subcategories; dev OTP login lands on `/admin`; the admin users and live dev
  OTP screens render; zero console/page errors.
- Live API checks: `/ready` → `{database: ok, redis: ok}`; a customer gets 403
  on `/admin/users`; role/permission updates are audited; self-demotion returns
  409.

## Phase 2 — Catalog and search (complete)

Verified 2026-10-26 with Neshan as the map provider.

- `Business` model + Alembic 0003 (PostGIS `geography(Point,4326)` + GIST index).
- `GET /businesses` with radius/category/text/cursor and sort modes (nearest/top/newest/urgent).
- `GET /businesses/{slug}` detail.
- Frontend search results + business detail + Neshan map tiles.
- Backend: 49 tests passing; frontend: `npm run build` passing.

## Phase 3 — Business onboarding (complete)

## Phase 4 — Reviews + rating aggregation (complete)

Backend: Review model, migration 0004, create review, moderation with rating
aggregation. Frontend: create business form. Gates pass.

## Phase 5 — Quote flow (complete)

QuoteRequest + Offer models (0005), create/offer/accept with `FOR UPDATE`,
ScheduledJob outbox (0006), outbox claim service, and `python -m app.worker`
sweeper. Gates pass (49 tests).

## Phase 6 — Notifications (complete)

DeviceToken/Notification/NotificationDelivery (0007), device + notification
endpoints, LogPushProvider, admin delivery log, owner panel page. Gates pass.

## Phase 7 — Permission-scoped admin + ads (complete)

Permission-gated moderation (`business.approve`, `review.moderate`), audit-log
endpoint, Ad model/endpoints (0008), Persian static pages. Gates pass.

## Phase 8 — Hardening (complete)

Permission-matrix tests, quote phone-leak test, coverage gate (72% ≥ 60%) in
CI. Playwright e2e left for a future pass (no suite yet).

## Phase 9 — Deploy

Not started. Follow the gates in `proposal.md` §7 and the deltas in
`session.md` §7. Notable non-negotiables: private license bucket, Postgres
outbox for quote dispatch, no web push, permission tests for every admin route.

## UI snapshots

Captured from the running dev build at 430px:

- [Home + category grid](screenshots/phase1-home.png)
- [Category bottom sheet](screenshots/phase1-category-sheet.png)
- [Admin dashboard](screenshots/phase1-admin.png)
- [Admin users](screenshots/phase1-admin-users.png)
- [Dev OTP viewer](screenshots/phase1-dev-otps.png)
