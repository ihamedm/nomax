# init - 2026-10-25T05:49:47.515Z


## 1. Locked decisions and their impact

| # | Decision | Impact |
|---|---|---|
| 1 | Tailwind + shadcn/ui | Already assumed; now explicit. shadcn components are vendored into `components/ui` |
| 2 | Mellipayamak; **dev bypass** with code read from admin dashboard | New `SmsProvider` interface; `DevOtpPage` in admin (superadmin + non-prod only); plaintext OTP mirrored in Redis only in dev |
| 3 | ArvanCloud S3 (dev + prod) | Single S3 storage adapter; two buckets: public images / **private licenses** |
| 4 | No web push; Android-native push in prod, log/delivery table in dev | Delete VAPID, `pywebpush`, `sw.js`, `DeviceSubscription`; add `DeviceToken` + `NotificationDelivery` + `PushProvider` |
| 5 | Broker + workers for quote flow | **Yes, but minimal**: Redis + `arq` (or Celery), one worker, no Kafka/RabbitMQ. Capacity math below |
| 6 | superadmin / admin / customer / owner | New RBAC layer, permission-scoped admin dashboard, audit log, admin shell needed in Phase 1 (dev OTP viewer lives there) |
| 7 | Modular frontend | Feature modules with public `index.ts`, enforced import boundaries, shared design-system layer |
| 8 | Bottom sheets, not modals | `vaul` (shadcn Drawer) primitive; modals and `window.confirm` banned |
| 9 | Android-like toasts | `sonner` styled as Android snackbar; no `alert()` |
| 10 | Local Vazirmatn | woff2 files committed, `@font-face`, preload, OFL license included |
| 11 | No runtime foreign APIs | Dependency matrix below; maps, monitoring, analytics, CI, registry all Iran-hosted or self-hosted |

**Important distinction:** foreign *build-time libraries* (React, FastAPI, Tailwind, arq…) are fine — they're bundled and never called at runtime. The rule applies to runtime service calls.

---

## 2. Runtime dependency matrix

| Need | Production | Dev/test | Rejected |
|---|---|---|---|
| SMS / OTP | Mellipayamak (pattern SMS) | `ConsoleProvider` — no network | Twilio, Kavenegar optional secondary |
| Object storage | ArvanCloud S3 | ArvanCloud S3, or `LocalStorage` for unit tests | **Storj**, AWS S3, MinIO |
| Push | Iranian provider (Pushe / Najva / Chabok) via adapter | `LogPushProvider` → `notification_deliveries` table + logs | FCM/Firebase, Web Push |
| Map tiles + geocode + routing | Neshan / Map.ir / Parsimap — **spike in Phase 0**, provider behind config | same adapter, or self-hosted fallback | Google Maps, Mapbox, OSM tiles as primary |
| Error tracking | GlitchTip (Sentry-SDK compatible, self-hosted) | local logs | Sentry SaaS |
| Uptime | Uptime Kuma (self-hosted) | — | UptimeRobot |
| Analytics | Umami self-hosted (site) + internal `business_views` | — | Google Analytics |
| Container images | ArvanCloud Container Registry / Docker Hub mirror | local cache | Docker Hub direct |
| CI | Gitea Actions / GitLab CE self-hosted (or GitHub + self-hosted runner) | local scripts | GitHub-hosted only |
| Fonts | committed local files | same | Google Fonts CDN |
| CDN / SSL | ArvanCloud CDN + SSL, or Let's Encrypt | mkcert | Cloudflare |
| Android distribution (future) | Cafe Bazaar / Myket | — | Google Play |

Open items: npm/PyPI mirror URLs are configurable (`.npmrc` / `pip.conf`), verified during Phase 0 rather than hardcoded now.

---

## 3. Point 5 — do you need a broker at 5,000 users?

No throughput problem exists at that scale. Do the math from your own KPIs: 2,000 accepted quotes/month at 10k users → roughly 200 requests/day at peak 20/hour, each fanning out to ~20–40 businesses → under ~1,000 push events/hour. A single worker handles this by orders of magnitude.

The real requirement is **scheduling and reliability**, not throughput:

- dispatch at 06:00 for night-time normal requests
- expiry at +2h / +24h
- retries for SMS/push providers
- no double-notification on worker restart

So: **Redis + arq**, one worker, one cron. Use a Postgres `scheduled_jobs` table as the source of truth (outbox), with a 30-second sweeper enqueuing due rows; workers are idempotent via `idempotency_key`. This survives Redis restarts and avoids dual-write bugs. Celery is an acceptable substitute if the team knows it better — same topology, no RabbitMQ. Don't introduce Kafka/RabbitMQ.

Note: OTP SMS stays **synchronous** (8s timeout, one retry, 503 on provider failure) because it's interactive; everything else is queued.

---

## 4. Data model and API deltas

**Remove:** `DeviceSubscription`, VAPID env vars, `public/sw.js`, `POST /notifications/subscribe` (VAPID), §5.3 of the proposal.

**Add / change:**

```python
class User:
    role: enum['customer', 'owner', 'admin', 'superadmin']
    # owner is auto-assigned on first business, downgraded when none remain
    # admins additionally receive granular permissions (relation or JSONB)

class DeviceToken:            # replaces DeviceSubscription
    user_id, provider: enum['pushe','najva','chabok'],
    token: str, platform: enum['android','web'],
    app_version: str, is_active: bool, last_seen_at

class NotificationDelivery:   # dev log + prod delivery audit
    notification_id, device_token_id, provider,
    status: enum['queued','sent','failed'], error, sent_at

class AuditLog:               # mandatory for multi-admin
    actor_id, action, entity_type, entity_id,
    before: JSONB, after: JSONB, ip, created_at

class ScheduledJob:           # outbox for delayed/reliable jobs
    type, payload: JSONB, run_at, status,
    attempts, idempotency_key, locked_at

class BusinessView:           # owner analytics without Google Analytics
    business_id, session_id, user_id?, created_at

class SmsLog:                 # Mellipayamak delivery auditing
    phone, purpose, provider_message_id, status, error
```

New endpoints replacing push ones:
- `POST /devices` — register native token (provider, token, platform)
- `DELETE /devices/{id}`
- `GET /notifications` + `PATCH /notifications/{id}/read` (in-app center stays)
- `GET /admin/dev/otps` — **superadmin + non-production only**, router not even mounted in prod
- `GET /admin/audit-log`, `GET /admin/users`, `PATCH /admin/users/{id}/role|permissions`

Additional database constraints beyond §3.3:
- partial unique `(user_id) WHERE status='active'` on quote requests
- unique `(business_id, user_id)` on reviews
- unique `(business_id, request_id)` on offers
- unique `(national_id)` and `(slug)` **where `deleted_at IS NULL`**
- unique `(provider, token)` on device tokens

---

## 5. Backend: RBAC + dev OTP

Permission matrix (implemented as `require_permission("business.approve")` dependencies, not ad-hoc role checks):

| Capability | customer | owner | admin | superadmin |
|---|---|---|---|---|
| Search, quote, review | ✓ | ✓ | ✓ | ✓ |
| Manage own business, offers, replies | — | ✓ | ✓ | ✓ |
| Approve business / verify license / moderate reviews | — | — | grantable | ✓ |
| Categories, suggestions, ads, stats | — | — | grantable | ✓ |
| Users, roles, permissions, settings, audit log, dev tools | — | — | — | ✓ |

- Admin scope is **per-permission**, assigned by superadmin, so "limited access to models" is enforceable per endpoint and per dashboard menu.
- `/auth/me` returns `role` + `permissions[]`; the admin nav is generated from it.
- First superadmin created by CLI (`nomax create-superadmin --phone ...`), never seeded with a default password/phone.
- Every admin mutation writes `AuditLog`.

**Dev OTP flow:** OTP verification uses an HMAC hash (prod). In non-prod, a second Redis key `dev:otp:{phone}` holds the plaintext for 120s. `/admin/dev/otps` lists active codes with copy + auto-fill; the login screen offers a "dev fill" button when `VITE_APP_ENV=local`. Triple guard: env check, superadmin permission, and router-level exclusion in production.

**Mellipayamak:** `SmsProvider` interface with `MelipayamakProvider`, `ConsoleProvider`; pattern-based send (`bodyId`), timeout + retry, `SmsLog` row per attempt. Start template/line approval in Week 1 — it's an external KYC step that can outlast the code.

---

## 6. Frontend system

```
src/
  app/            # providers, router, layouts, error boundary
  components/
    ui/           # shadcn primitives (vendored)
    patterns/     # BottomSheet, AppBar, TabBar, Toast, EmptyState,
                  # ErrorState, Skeletons, PullToRefresh, SafeArea
  features/
    auth/ business/ quote/ review/ admin/ notifications/
      api/ components/ hooks/ schemas/ stores/ index.ts
  lib/            # api client, jalali date, digits, permissions, platform
```

Rules enforced by `eslint-plugin-boundaries`: features import only through `index.ts`; `ui`/`patterns` never import features; no business logic in route components; page files only compose. Stories/tests colocated (Storybook optional in Phase 8).

- **Bottom sheets:** `vaul`-based `BottomSheet` with snap points, drag handle, safe-area insets, and back-button dismissal. All filters, quote steps, and destructive confirmations use it. Desktop fallback: side sheet.
- **Toasts:** `sonner` restyled as Android snackbar — bottom-aligned above the tab bar, dark surface, icon, 2–4s, swipe to dismiss, max 3 stacked. `window.alert/confirm` banned in review.
- **Mobile-first**: 48px targets, `env(safe-area-inset-*)`, no hover-only affordances, pull-to-refresh, infinite scroll instead of pagination buttons, sticky bottom nav.
- **Fonts:** Vazirmatn variable woff2 under `public/fonts/`, `@font-face` + `<link rel=preload>`, `font-display: swap`, OFL license committed.
- **Persian details:** `dir="rtl"`, Tailwind logical properties, Persian digit conversion utilities, Arabic-Indic digit normalization for phone/national ID inputs, **Jalali dates** (`date-fns-jalali`) with Tehran timezone.
- **Android-readiness:** isolate push token, back-button, haptics, and app-version behind `lib/platform/` so a Capacitor (or native WebView) wrapper can be added later without touching features.

---

## 7. Revised roadmap

| Phase | Weeks | Theme | Gate |
|---|---|---|---|
| 0 | 1 | Foundations, design system, provider ADRs | Compose up; seeded categories render; BottomSheet/Toast/Vazirmatn live |
| 1 | 1–2 | Auth, Mellipayamak, RBAC, admin shell, **dev OTP** | Login via dashboard-read OTP; permissions enforced |
| 2 | 3–4 | Catalog, seed, PostGIS search, **Iranian map provider** | Geo search works with Neshan/Map.ir tiles |
| 3 | 5–6 | Business onboarding, uploads (Arvan S3), moderation | Register → approve → search, with audit log |
| 4 | 7–8 | Reviews + rating aggregation | Cached rating correct after approve/reject |
| 5 | 9–10 | Quote flow + worker/outbox | All quote tests + phone-leak test pass |
| 6 | 11 | Notification center, provider adapter, owner panel | Push logged/delivered; no web-push anywhere |
| 7 | 12–13 | Full permission-scoped admin, ads, utility | Every §4 endpoint + permission test |
| 8 | 14–15 | Hardening, e2e, security, coverage | 80%/60% gates, Playwright green |
| 9 | 16 | Iranian VPS deploy, Arvan, self-hosted observability | HTTPS, restore drill, GlitchTip, Uptime Kuma |

Free time from dropping web push (~3–4 days) goes into RBAC, admin shell, and Android-ready UI.

### Phase deltas vs v1

- **Phase 0:** Storage/SMS/Push/Map provider interfaces + ADRs; local fonts; BottomSheet + Toast primitives; Jalali/digit utilities; Arvan S3 bucket setup; registry mirror config; validate boto3 against Arvan S3 (path-style, presign host quirks).
- **Phase 1:** now includes RBAC and the admin shell, because the dev OTP viewer needs it; Mellipayamak provider + console provider + `SmsLog`; superadmin CLI.
- **Phase 2:** map provider spike and Leaflet tile configuration replace hardcoded OSM; geocoding for business location; routing button → Iranian provider link.
- **Phase 3:** `StorageBackend` with public/private buckets; license presigned URLs for admins only; upload goes through API (compression) with `client_max_body_size 6m`; audit log on approve/reject/toggle-24h.
- **Phase 5:** arq + Postgres outbox; idempotent dispatch; night 06:00 deferral; sweeper for expiry; `SELECT ... FOR UPDATE` on accept; exclude requester's own business from dispatch.
- **Phase 6:** no VAPID/service worker; `DeviceToken`, `NotificationDelivery`, `LogPushProvider`; admin page to inspect delivery logs; notification center.
- **Phase 7:** every admin screen permission-gated; ads; contact; QR; Persian static pages; admin users/permissions/audit screens.
- **Phase 8:** add permission-matrix tests, PII/log review (phone, national ID), provider-outage behavior, offline/slow-network UX, queue-depth and dead-letter checks.
- **Phase 9:** Arvan S3 + CDN, Arvan registry, GlitchTip + Uptime Kuma + Umami, backup to Arvan bucket **plus restore drill**, Docker mirror; remove all foreign SaaS from the DoD (replaces "Sentry" in §14).

---

## 8. Updated risks

1. **Map provider is now a real dependency** — Neshan/Map.ir keys, tile terms, and quota must be confirmed in Week 1; otherwise Phase 2 stalls. Keep a self-hosted OSM fallback path.
2. **Mellipayamak pattern approval/KYC** can take days–weeks; console provider keeps dev unblocked.
3. **Dev OTP endpoint is a production footgun** — mitigate with router-level exclusion, not just a permission check.
4. **RBAC drift** — permission strings in one module, tested against the route table; a test asserts no admin route lacks a permission dependency.
5. **Queue reliability** — delayed jobs in Redis alone can be lost; the Postgres outbox is non-optional.
6. **Arvan S3 client quirks** — signature/path-style/presign host differences; validate in Phase 0, not deploy week.
7. **Iran-network package installs** — pin lockfiles, mirror config, and pre-pull Docker images to avoid a deploy blocked by a registry.
8. **License image privacy** — a public bucket leak would expose trade documents; separate buckets and no public serializer for license keys.
9. **Owner role flapping** — define downgrade behavior explicitly (recommend: downgrade only when no non-deleted business remains).
10. **Analytics definitions** — decide what counts as a "view" in Phase 6 or the owner dashboard will show fabricated numbers.

---

## 9. Week-1 backlog (updated)

1. Scaffold + Compose (`db`, `redis`, `api`, `worker`, `web`) + Alembic + CI.
2. Provider interfaces and ADRs: storage, SMS, push, map, queue.
3. `core/config.py` with environment profiles (`local|test|staging|production`), response envelope, `/health`, `/ready`.
4. Design system: Tailwind config, RTL setup, local Vazirmatn, BottomSheet, Toast, Jalali/digit utils.
5. RBAC skeleton: roles, permission registry, `require_permission`, superadmin CLI.
6. Admin shell + dev OTP viewer + Mellipayamak/console providers.
7. Extract `categories.json` (18 + 150+) and seed idempotently.
8. Walking skeleton: dev OTP login → categories → home grid, in Compose.

---

## 10. Questions before this becomes a tracked plan

1. By "read the token from admin dashboard" — do you mean the **OTP code**, not a JWT? (I've assumed OTP code.)
2. Which **map provider** do you already have access to: Neshan, Map.ir, or Parsimap? This is the only genuinely blocking item for Phase 2.
3. Which **push provider** should the adapter target first: Pushe, Najva, or Chabok? Signup/KYC can start now even though code lands in Phase 6.
4. Admin access: **custom per-admin permissions** (my recommendation) or fixed presets like "Moderator" / "Content manager"?
5. Is **GitHub** usable for CI, or should the pipeline target a self-hosted Gitea/GitLab? And do you already have a VPS/Arvan account?
6. Future Android: **Capacitor wrapper** around this web app, or a separate native app consuming the API? It changes how much platform abstraction we build now.