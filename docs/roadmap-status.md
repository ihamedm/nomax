# NOMAX roadmap status

Last updated: 2026-10-31

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

## Post-v1 — Full quote ecosystem (2026-10-31)

The quote flow is no longer a stub: customer, owner and superadmin now have
complete screens on top of the existing quote/offer tables.

### Customer

- `/quote/new` is a three-step RTL form. Step 1 reuses the add-business
  category/subcategory bottom sheet; step 2 reuses the Neshan map picker with
  quote-specific copy; step 3 adds the optional 2-hour urgent toggle and notes.
  The mobile app nav is hidden while the wizard is open, and the sticky action
  bar remains visible.
- `/quote/mine` (also `/me/quotes`) shows the current request with a live
  countdown and offer count, a waiting state when no offer has arrived, and a
  collapsible history for accepted/cancelled/expired requests.
- `/quote/mine/:id` compares offers by business, rating, price, unit, brand and
  message. Accepting requires confirmation, reveals only the selected business's
  phone, expires competing offers, and notifies the owner. Active requests can be
  cancelled; pending offers are expired and their owners are notified.
- One active request per customer remains enforced by the partial unique index;
  the form turns a conflict into a link to the existing request.

### Owner

- `/me/customers` now has three tabs:
  - **جدید** — active matching requests without an offer from the owner's
    businesses; decline or open the offer sheet.
  - **مشتریان** — offers accepted by the customer, with the customer name/phone
    and a call action.
  - **بایگانی** — sent offers awaiting a response, declined requests, lost
    offers, and closed requests.
- The offer sheet collects price, unit, brand and a message; when the owner has
  multiple matching businesses it asks which business is bidding.
- The new tab only includes approved businesses matching category/subcategory and
  the 10km radius. Owner list/detail responses never include the customer phone
  before acceptance.

### Superadmin

- `/admin/quotes` (permission `quote.read`) provides stats — total, active,
  urgent, accepted, acceptance rate, total/pending offers — plus status filters,
  search, pagination, a request/offer detail modal, and cancel (`quote.manage`)
  with an audit-log entry and owner notifications.
- Dashboard and sidebar entries are permission-scoped.

### Backend and data

- `GET /quotes/requests/mine` now includes category/subcategory,
  `offers_count` and the accepted business. `GET /quotes/requests/incoming`
  accepts `scope=new|archive|customers` and returns counts, matching businesses
  and the owner's offer.
- New `GET /quotes/{id}` scopes offers to the customer, winner or admin; new
  owner decline endpoint; offer payloads include unit and status.
- `POST /quotes/offers` validates positive price, matching business and
  duplicate bids. `PATCH .../accept` expires other pending offers and notifies
  the winner.
- Notifications are typed (`quote_request`, `quote_offer`, `quote_accepted`,
  `quote_cancelled`) and link to the quote/customer screens.
- Lazy expiry on reads marks overdue requests/offers expired without requiring
  the worker.
- Migration `0019` adds `offers.unit` and quote status/created indexes.
- New tests in `backend/tests/test_quote_flow.py`; **147 backend tests** and
  **28 frontend Vitest tests** pass. Browser E2E covered the full form → owner
  offer → customer accept → phone reveal flow, plus the admin dashboard.

## Post-v1 — Reliable multi-wave quote dispatch (2026-10-31)

The one-shot dispatcher was replaced after two reproducible failure classes:
UTC quiet-hour checks dropped requests created in the morning in Tehran, and an
exact subcategory filter could exclude every approved business in the parent
category. A third issue was that no owner was retried when the first delivery
went unanswered.

### Dispatch engine

- `quote_requests` is now the durable schedule (`dispatch_round`,
  `dispatch_status`, `last_dispatched_at`, `next_dispatch_at`).
  `quote_deliveries` records `round`, `source` (`auto`/`manual`) and
  `responded_at`; `quote_dispatch_runs` audits each wave.
- Candidate ladder: exact subcategory + tight radius → category + tight radius
  → expanded radius → category-wide fallback. Distance and subcategory fallbacks
  are dashboard toggles.
- Waves target unique owners (one business per owner) with configurable initial
  and retry batch sizes, minimum target and max rounds. Contacted owners are
  never repeated.
- A silent wave expands. Seen-without-offer expansion is a toggle. A pending
  offer stops auto-expansion. No-candidate requests stay `searching` and are
  rescanned without consuming a delivery round.
- Quiet hours are evaluated in `Asia/Tehran`. Urgent night requests prefer 24h
  businesses, then widen instead of waiting until morning.
- Redis Streams + a delayed sorted set wake the worker; the worker also scans
  `next_dispatch_at` in Postgres every few seconds. Lost messages, Redis
  restarts and worker restarts are therefore recoverable. Request ids are
  locked separately to avoid Postgres outer-join `FOR UPDATE` errors.

### Admin and customer surfaces

- `/admin/settings?tab=dispatch` controls enablement, batch sizes, max rounds,
  response windows, seen expansion, radii, fallbacks, sending hours, night
  urgent policy and no-candidate rescan interval.
- The header’s «راهنمای ارسال استعلام» button opens a single Persian help modal:
  visual flow (window → candidate ladder → wave → wait → decision/retry/end),
  five decision rules, a variable glossary using the exact settings labels, and
  a timed worked example. It is responsive on mobile.
- `/admin/quotes` detail now shows dispatch waves, per-owner delivery/seen/offer
  status, source and round. `quote.manage` can add approved owners manually
  (search + multi-select, de-duplicated, audited) or force the next wave.
- Customer quote list/detail renders a compact status graph: ثبت → ارسال →
  مشاهده → پیشنهاد with counts, current/max wave and next-wave countdown.
  Owner identities stay hidden until an offer is submitted.
- Fallback-delivered owners can open and answer the request even if their
  subcategory/radius differs; only real deliveries are marked seen.

### APIs and data

- `GET /admin/settings`, `PUT /admin/settings/quote_dispatch`.
- `GET /admin/quotes/{id}/dispatch`, `POST /admin/quotes/{id}/assign`,
  `POST /admin/quotes/{id}/dispatch-now`.
- `GET /quotes/requests/mine` and `GET /quotes/{id}` include an aggregate
  `dispatch` object (counts, state, waves, timing).
- Migration `0021` adds the dispatch columns, delivery audit fields and
  `quote_dispatch_runs`; it backfills delivered waves and schedules previously
  dropped active requests for immediate recovery.
- Tests: `backend/tests/test_quote_dispatch.py` covers Tehran quiet hours,
  subcategory fallback, urgent-night fallback, multi-wave expansion/max rounds,
  seen-without-offer, no-candidate recovery, worker reconciliation, manual
  assignment and settings validation — **147 backend tests**, **28 frontend
  Vitest tests**, typecheck/build pass.
- Screenshots: `admin-settings-dispatch.png`, `admin-quote-dispatch.png`,
  `quote-dispatch-status.png`, `admin-dispatch-help.png`,
  `admin-dispatch-help-variables.png`, `admin-dispatch-help-mobile.png`.

## Post-v1 — Analytics dashboard and demand tracking (2026-10-31)

New `/admin/analytics` page (permission `stats.read`) with three tabs. All
timestamps are grouped in Tehran time; calendar week starts on Saturday.

### General tab

- Widgets: businesses (total/approved), reviews, quotes, searches, users and
  the sum of actionable items.
- 14-day multi-line chart: searches, quote requests, quote responses and
  registrations.
- Quote-funnel grouped bars for today / this week / this month / all time:
  requests → sent to owners → seen → responded → chosen.
- Today's 24-hour bar chart for searches and quote requests.
- Role-composition donut with role flags and counts.
- Pending-action chart for businesses, reviews and unanswered active quotes.

### Quotes tab

- Widgets for total/active/accepted quotes, offers, pending offers, seen and
  responded requests, response/choice rates and average timing.
- Status donut for active / accepted / cancelled / expired.
- Timing bars for request → sent to owner, seen by owner, first offer, and
  customer choice, with sample counts.
- Feedback bars comparing seen / responded / chosen percentages.

### Market and demand

- Demand = searches + quote requests per category.
- Top-category demand-vs-supply bars.
- Full category table: businesses, searches, no-result searches, quotes,
  active unanswered quotes, demand, and verbose status (`جذب فوری`,
  `کمبود عرضه`, `متعادل`, `عرضه مازاد`, `بدون تقاضا`, `بدون عرضه`).
- Most-wanted subcategory table with searches, quotes and businesses.
- Most-searched keyword table with searches, average visible results and
  no-result counts.
- No-result keyword table with search count and related category.

### Instrumentation

- `search_logs` stores first-page search events only (cursor pages are not
  logged) with query, inferred category/subcategory, result count and user.
- `quote_deliveries` records each quote/business dispatch; `seen_at` is set when
  the owner inbox renders the request. `quote_requests.accepted_at` records the
  customer choice.
- `GET /admin/analytics/overview`, `/quotes`, `/market`, `/businesses`, `/map`,
  `/logs` and `/logs/summary` expose the aggregates; `/admin/data` also exposes
  the two new tables.
- Migration `0020` adds `search_logs`, `quote_deliveries` and
  `quote_requests.accepted_at` (backfilled from accepted offers).
- **147 backend tests** and **28 frontend Vitest tests** pass. Browser checks at
  1440/1280/1024 widths showed no console errors or horizontal body overflow.

### Business, map and event-log tabs

- **Businesses**: sortable performance table with category/subcategory, views,
  sent/accepted offers, response-rate bars, rating, negative-rate bars and
  operational status labels. Search filters the table locally; every column
  header toggles ascending/descending order.
- **Map**: full-height Neshan map with green business pins, sky normal-quote
  pins and red urgent-quote pins; layer toggles and counts, popups and a
  city-centred initial viewport.
- **Logs**: derived raw event stream (search, registration, business creation,
  review, quote request/offer/seen/chosen) with type filter, 25-row pagination,
  14-day event volume line chart and type donut.
- New endpoints: `GET /admin/analytics/businesses`, `/map`, `/logs` and
  `/logs/summary`, all `stats.read`.
- The analytics page is lazy-loaded so the main customer bundle remains below
  the 500kB warning threshold.
- Screenshots: `analytics-businesses.png`, `analytics-map.png`,
  `analytics-logs.png`, `analytics-logs-table.png`.

Remaining deliberate gaps: Playwright e2e, whole-app frontend coverage, Persian
slugs, and Mellipayamak KYC (external).

## Post-v1 — UX polish, gallery and desktop navigation (2026-10-31)

### Search and categories

- Search input autofocuses on every `/search` mount (cold load and mobile) and
  keeps a clear button.
- Query updates are debounced for 450ms after the last keystroke. A live check
  typed a six-character Persian query and produced one `/businesses` request.
- The category picker has one inline search field that filters categories and
  all subcategories together. It normalises Persian/Arabic characters and uses
  one cached `/categories/subcategories` catalog, so filtering is local.

### Business gallery

- Added `business_images` (URL, sort order, main flag) and migration `0022`;
  existing `profile_image_url` values are backfilled as the first image.
- `MAX_BUSINESS_IMAGES` (default 6) configures the limit through `.env`; the
  value is exposed by `/me/businesses` and consumed by the wizard.
- Owners can upload up to six photos at once, remove photos, and choose the
  main photo from the add/edit-business wizard. The editor is a fixed 3×2 grid.
  `profile_image_url` follows the selected main image for cards and search.
- Public business detail renders the gallery as a swipeable, arrow-and-dot
  carousel. Any slide opens a full-screen lightbox with keyboard, thumbnail and
  swipe navigation; single images also open the lightbox, and empty galleries
  get a branded placeholder.

### Business detail redesign

- The detail page now leads with a clean gallery hero, followed by category,
  name, rating, verification/24h chips and the short description. The local
  “جزئیات کسب‌وکار” header was removed in favour of the global back action.
- Call and Neshan directions are a clear primary/secondary button pair; saving
  is a compact bookmark control on the hero.
- `GET /businesses/{slug}` returns `owner: {name, phone}`. A dedicated owner
  card shows the name, avatar initial and a tap-to-call phone chip; owners keep
  their edit shortcut.
- About content (description, address, Instagram) was consolidated into one
  calm card. Reviews and map behavior are unchanged.

### Navigation and form ergonomics

- Desktop header now shows Home, Categories, Search and Quotes links at `md+`;
  the floating bottom toolbar remains mobile-only.
- Add/edit-business and quote wizards use a close (×) header action that
  replaces history with `/me/businesses` or `/quote/mine`, instead of a back
  arrow.
- Wizard content has extra bottom padding so sticky action bars never cover
  the last form fields.
- Business pins in search map mode open a sticky bottom business card via an
  opt-in `NeshanMap.onMarkerClick` callback.

**Verification:** 149 backend tests, 28 frontend Vitest tests, typecheck and
production build pass; migration `0022` applied. Browser checks at 1440×1000
and 390×844 covered desktop nav, autofocus/debounce, category search, the
six-photo 3×2 editor, the detail carousel/lightbox and owner card, map card and
close routing.

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
- [Customer quote list](screenshots/quote-customer-list.png)
- [Customer offer comparison](screenshots/quote-customer-detail.png)
- [Customer accepted request](screenshots/quote-customer-accepted.png)
- [Owner new requests](screenshots/quote-owner-new.png)
- [Owner accepted customers](screenshots/quote-owner-customers.png)
- [Owner archive](screenshots/quote-owner-archive.png)
- [Owner offer sheet](screenshots/quote-owner-offer-sheet.png)
- [Quote form — step 1](screenshots/quote-form-step1.png)
- [Quote form — step 2](screenshots/quote-form-step2.png)
- [Quote form — step 3](screenshots/quote-form-step3.png)
- [Admin quote dashboard](screenshots/admin-quotes.png)
- [Analytics — general](screenshots/analytics-general.png)
- [Analytics — general lower charts](screenshots/analytics-general-bottom.png)
- [Analytics — quotes](screenshots/analytics-quotes.png)
- [Analytics — market demand](screenshots/analytics-market.png)
- [Analytics — category table](screenshots/analytics-market-table.png)
- [Analytics — keyword tables](screenshots/analytics-market-keywords.png)
- [Analytics — business performance](screenshots/analytics-businesses.png)
- [Analytics — market map](screenshots/analytics-map.png)
- [Analytics — event logs](screenshots/analytics-logs.png)
- [Analytics — raw event table](screenshots/analytics-logs-table.png)
- [Dispatch strategy settings](screenshots/admin-settings-dispatch.png)
- [Dispatch help — overview and flow](screenshots/admin-dispatch-help.png)
- [Dispatch help — variable glossary](screenshots/admin-dispatch-help-variables.png)
- [Dispatch help — mobile](screenshots/admin-dispatch-help-mobile.png)
- [Admin dispatch waves and manual assignment](screenshots/admin-quote-dispatch.png)
- [Customer dispatch status graph](screenshots/quote-dispatch-status.png)
- [Customer dispatch graph — mobile](screenshots/quote-dispatch-status-mobile.png)
- [Search on desktop with header navigation](screenshots/search-desktop-header.png)
- [Category picker inline search](screenshots/category-picker-search.png)
- [Category and subcategory search results](screenshots/category-picker-search-results.png)
- [Business photo editor](screenshots/business-gallery-editor.png)
- [Public business gallery](screenshots/business-gallery-detail.png)
- [Business detail hero and carousel](screenshots/business-detail-hero.png)
- [Gallery lightbox](screenshots/business-gallery-lightbox.png)
- [Actions and owner card](screenshots/business-detail-actions-owner.png)
- [Business detail on desktop](screenshots/business-detail-desktop.png)
- [Business map pin bottom card](screenshots/map-business-sheet.png)
- [Form header close action](screenshots/form-close-header.png)
