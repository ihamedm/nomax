# NOMAX roadmap status

Last updated: 2026-10-29

This file is the hand-off point between agent sessions. Update it at the end of
every working session so the next agent knows what actually runs.

## Phase 0 — Foundations

| Item | Status | Notes |
|---|---|---|
| Compose: Postgres/PostGIS + Redis | ✅ | `docker compose up -d`; ports 5433 / 6380 |
| ArvanCloud S3 + health | ✅ | `S3_*` env in `.env`; `/ready` reports storage; `nomax-public` / `nomax-private` buckets |
| Alembic baseline + 0002 catalog/sms | ✅ | `alembic upgrade head` |
| Response envelope + `/health` + `/ready` | ✅ | `/ready` checks DB, Redis and configured S3, returns 503 when degraded |
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

## Phase 9 — Deploy (complete)

Dockerized api/worker/web, production compose with Caddy TLS, backup script +
systemd timer, restore drill executed, healthchecks, and the Uptime Kuma /
GlitchTip observability compose. HTTPS is configured for the production domain.

## Phase 10 — Final verification (complete)

- Backend: 69 tests passing, coverage 68.6% (gate 60%).
- Frontend: `npm run build` and `npm run test` passing (91.9% on tested lib modules).
- Added §4 endpoint smoke coverage in `backend/tests/test_endpoints_coverage.py`.
- Fixed spec-path mismatches: `/me/businesses`, `/me/businesses/{id}/analytics`,
  `/me/notifications`, `/uploads/image`.
- Suggestion approval now actually creates the category/subcategory.
- Frontend `/me` area (profile, businesses, edit, notifications, analytics) and
  TanStack Query for server state.
- Dev/prod compose fixes: added `python-multipart` (upload route crashed API at
  import), api healthcheck, and worker now waits for api healthy so it cannot
  race migrations.
- Admin: superadmin can create a new admin by phone (`POST /admin/users`) and
  assign per-module permissions from `/admin/users`; dashboard shows stats.
- README links the user (`/me`) and admin (`/admin`) dashboards.
- App redesign: sticky app header with menu/back + user icon, drawer, floating
  mobile bottom nav, home hero/search, 3-column categories, new/most-visited
  carousels, ad slots, AJAX search with admin-managed trending terms.
- CMS: shared data-table module, categories/tags/ads/settings screens, and a
  superadmin generic data CRUD page (`/admin/data`). Migration 0015 adds
  `businesses.view_count` and `app_settings`.
- UI polish: sliding drawer transition, RTL back chevron, equal-height carousel
  cards, icon-only search buttons, padded `/me` with logout, and persisted
  light/dark theming (system default, switch in the drawer and admin header).
- Account navigation: home, my business, customers, quotes and saved. The
  customers screen lists incoming quote requests; quotes lists the user's
  requests; saved uses the new `bookmarks` table (migration 0016) with a
  save/un-save action on business details.
- Storage: MinIO removed; development and production both use ArvanCloud S3
  through boto3 with path-style addressing. Added `/admin/files` for listing,
  creating and deleting files/folders in the public/private buckets, and a
  `storage.manage` permission.

## Post-v1 — Add-business wizard (2026-10-28)

- `/businesses/new` is now a five-step RTL wizard: business details, contact
  and address, optional data, services and final preview. A sticky header shows
  `گام ۱ از ۵` on the right and the step label on the left. The step actions are
  pinned to the bottom and the mobile toolbar is hidden on this route.
- Category picker: bottom sheet with the category list and a subcategory panel
  that slides in from the left; the dashed trigger shows `category > subcategory`.
- Address step: read-only owner phone, the 24h warning panel, and a full-screen
  Neshan map picker. Addresses are geocoded through the new `/api/v1/geo/search`
  and `/api/v1/geo/reverse` proxy (Nominatim by default) with a draggable pin.
- Optional step: picture upload, collapsed owner identity box, 120-character
  intro, shop phone, Instagram, and the disabled "license coming soon" panel.
- Services step: subcategory standard tags are pre-selected and removable; up to
  four custom tags can be added. Standard tags are stored as approved catalog
  tags, custom ones as pending.
- Preview step: section summaries, edit shortcuts, rules bottom sheet and an
  explicit rules-acceptance checkbox before submission.
- `/businesses/:id/edit` reuses the same five-step wizard with the business
  pre-filled (picture, category, geo, tags, contact fields); rules are shown as
  already accepted and the final action reads «ذخیره تغییرات».
- Owners are capped at `MAX_BUSINESSES_PER_OWNER` active businesses (default 1).
  The API returns `can_create` with `/me/businesses`; the profile hides «ثبت
  جدید» and `/businesses/new` shows a limit notice once reached.
- Address search is bounded to the Behbahan city viewbox by default, so map
  results cannot drift to other cities.
- Backend: `POST /businesses` accepts `profile_image_url` and `tags`, validates
  subcategory/category pairing, coordinates and phone numbers, and auto-approves
  standard tags. 126 backend tests passing.

## Post-v1 — In-app messages and rejection UX (2026-10-28)

- In-app messages are stored in `notifications` with the receiver in
  `user_id`; they are deliberately separate from push delivery
  (`device_tokens` / `notification_deliveries`).
- Rejecting a business requires a reason and queues a message to its owner with
  the business name, reason and an edit link. Approving queues an approval
  message. Both admin endpoints and the generic status PATCH do this.
- Owners see unread badges on the header user icon and on the `/me`
  notifications card. `/me/notifications` lists messages with type chips,
  mark-one/mark-all read, and a direct «اصلاح و ارسال دوباره» action for
  rejection messages.
- Rejected businesses remain hidden from the public (404) but are visible to
  their owner and admins at `/businesses/{slug}`, with a rejected badge, the
  rejection reason and an owner edit action. Any owner edit clears the reason
  and puts the business back into `pending`.
- Admin `/admin/notifications` composes announcements to all users, owners,
  customers or a single receiver, with an optional destination link.
- `GET /me/notifications/unread-count`, `PATCH /me/notifications/read-all`,
  `PATCH /notifications/{id}/read`, `POST /admin/notifications/broadcast`.
- 126 backend tests passing; frontend typecheck/build/Vitest passing.

## Post-v1 — Upload organization and image pipeline (2026-10-28)

- User business images now live under `uploads/businesses/{user_id}/{YYYY}/{MM}/`
  instead of the upload root. Local fallback directories are preserved and
  served at `/uploads/*`; S3 keys use the same structure.
- The backend image pipeline handles EXIF orientation, optional filters
  (`none`, `warm`, `cool`, `vivid`, `mono`, `soft`), crop anchors, JPEG
  compression, and named crops: `square` 800², `card` 640×360, `wide`
  1200×600 and `thumb` 200². The main image is capped at 350KB.
- `POST /uploads/image` accepts `crop`, `filter` and `anchor`; the response
  returns the main image plus variant URLs/dimensions. The matching crop reuses
  the main object to avoid duplicate storage.
- Admin file-manager uploads (`/admin/files/upload`) deliberately bypass image
  processing and remain raw.
- The add-business wizard compresses large photos in the browser (max 1600px,
  JPEG quality ~86%) before uploading; the backend still always re-processes.
  Input is capped at 15MB and the post-compression upload at 5MB.
- 126 backend tests passing; frontend typecheck/build/Vitest passing.

## Post-v1 — Reviews and private feedback (2026-10-29)

- Reviews can now be submitted from the business page in a bottom sheet with a
  five-star rating, optional text and a private checkbox.
- Public reviews remain `pending` until admin approval or owner approval and
  only then count toward `rating_avg` / `rating_count`. Rejection/pending
  recalculates the aggregate. Owners can moderate and reply from `/me/reviews`.
- Private reviews use `status=private` + `is_private=true`: visible only to the
  business owner (and never public, never in the admin moderation queue, and
  blocked by the moderation endpoint).
- Owners have `/me/reviews` listing pending, private and approved reviews for
  their businesses, with mark-seen and an unread count. The `/me` profile gets a
  «نظرات» card and the header user-icon badge now aggregates unread messages
  and unseen reviews.
- Added migration `0017_review_privacy` (`is_private`, `owner_seen_at`), and
  duplicate/self-review guards. Review text is capped at 300 characters.
- Migration `0018` recalculates all business ratings from approved public
  reviews (removing fabricated demo ratings); demo seed no longer writes them.
- Admin `/admin/reviews` now lists all reviews with business/status filters,
  search, pagination and approve/decline actions. Stars are compact and the map
  stacking no longer covers the review bottom sheet.
- 126 backend tests passing; frontend typecheck/build/Vitest passing.

## Post-v1 — Login redirects and compact dashboard (2026-10-29)

- Signed-out review actions now open a bottom-sheet login prompt instead of a
  bare link. «ورود / ثبت‌نام» goes to `/login?next=<business>`, and after OTP
  the user returns to the same business with the review form already open.
- The review intent travels in router state, keeping the URL clean and
  preventing the sheet from reopening on refresh.
- All auth-gated routes (`/me/*`, `/admin/*`, quote create/list, business
  create/edit) preserve the attempted path and query (including pagination)
  through login. Redirect targets are validated as same-origin paths only.
- Saving a business uses the same login prompt; the header account icon still
  routes to the role-appropriate home after login.
- Admin dashboard density was reduced for laptop screens: 240px sidebar, 56px
  header, tighter main padding, scoped 13px/11px type scale, 40px inputs and
  primary buttons, denser table rows. Customer screens are unchanged.
- Frontend Vitest is now **15 tests**; backend remains **126 tests**. Browser
  verification at 1440×900 covered the full logged-out → OTP → review-form
  return flow and the admin dashboard/reviews/businesses screens.
- Screenshots: `login-required-review.png`, `review-after-login.png`,
  `admin-compact-dashboard.png`, `admin-compact-reviews.png`,
  `admin-compact-businesses.png`.

Remaining deliberate gaps: Playwright e2e, whole-app frontend coverage, Persian
slugs, and Mellipayamak KYC (external).

## UI snapshots

Captured from the running dev build at mobile widths (430–500px):

- [Home + category grid](screenshots/phase1-home.png)
- [Category bottom sheet](screenshots/phase1-category-sheet.png)
- [Admin dashboard](screenshots/phase1-admin.png)
- [Admin users](screenshots/phase1-admin-users.png)
- [Dev OTP viewer](screenshots/phase1-dev-otps.png)
- [Add-business wizard — step 1](screenshots/wizard-step-1.png)
- [Edit-business wizard — prefilled](screenshots/wizard-edit-step-1.png)
- [Add-business wizard — step 3](screenshots/wizard-step-3.png)
- [Add-business wizard — services](screenshots/wizard-step-4.png)
- [Add-business wizard — map picker](screenshots/wizard-map-picker.png)
- [Add-business wizard — rules sheet](screenshots/wizard-rules.png)
- [Profile with unread message badges](screenshots/messages-profile.png)
- [In-app message inbox](screenshots/messages-inbox.png)
- [Rejected business — owner view](screenshots/business-rejected-owner.png)
- [Admin announcement composer](screenshots/admin-announcements.png)
- [Profile with review badge](screenshots/reviews-profile-badge.png)
- [Owner review inbox](screenshots/reviews-owner-inbox.png)
- [Public business reviews](screenshots/reviews-public-business.png)
- [Add-review bottom sheet](screenshots/reviews-add-bottom-sheet.png)
- [Admin review list](screenshots/admin-reviews.png)
- [Login-required review prompt](screenshots/login-required-review.png)
- [Review form after login](screenshots/review-after-login.png)
- [Compact admin dashboard](screenshots/admin-compact-dashboard.png)
- [Compact admin reviews](screenshots/admin-compact-reviews.png)
- [Compact admin businesses](screenshots/admin-compact-businesses.png)
