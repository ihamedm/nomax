# NOMAX — implementation verification checklist

Source of truth: `proposal.md` (original v1) with overrides from `session.md` and
`docs/adr/*` (no web push, superadmin, Neshan, Mellipayamak, outbox).
Status: `[x]` verified implemented, `[~]` partial, `[ ]` missing / to verify.

## A. Non-negotiable business rules (§2)

- [x] A1 Anonymous quote: customer phone hidden until offer acceptance
- [x] A2 Phone revealed only to accepted business (`phone_revealed_to`)
- [x] A3 One active quote request per user (DB partial unique)
- [x] A4 Dispatch window: normal 06–21 Tehran; urgent at night prefers `is_24h`, then widens so it is not stranded
- [x] A5 Expiry: urgent +2h, normal +24h
- [x] A6 Business lifecycle pending → approved/rejected(reason); pending hidden from public search/detail, rejected visible to its owner with reason; rejection sends an in-app message and a rejected owner edit resubmits to pending (tests: `test_admin_rejects_business_with_reason`, `test_only_approved_businesses_are_searchable`, `test_rejected_business_visible_to_owner_only`, `test_owner_edit_resubmits_rejected_business`)
- [x] A7 `is_verified` only via admin + valid license
- [x] A8 `is_24h` user-set, admin toggle on abuse
- [x] A9 One business per `national_id` and per-owner cap (`MAX_BUSINESSES_PER_OWNER`, default 1)
- [x] A10 National ID + phone read-only from verified profile
- [x] A11 Reviews pending → approved/rejected (tests: `test_rating_updates_on_approval`, `test_rejected_review_is_hidden_and_not_rated`)
- [x] A12 Max 4 custom tags per business (subcategory standard tags auto-approved on create; ≤30 total)
- [x] A13 18 categories / 150+ subcategories seeded (188)
- [x] A14 Category suggestions → admin

## B. Data model (§3)

- [x] B1 `created_at`/`updated_at`/`deleted_at` on every table
- [x] B2 User fields (phone, national_id, full_name, role, verified, last_login_at)
- [x] B3 Business (License via `licenses.business_id`; PostGIS geo in 0003)
- [x] B4 License
- [x] B5 Category / Subcategory
- [x] B6 Tag / BusinessTag
- [x] B7 Review (text/comment, author_name, reply, replied_at)
- [x] B8 QuoteRequest (subcategory, address, neighborhood, geo, is_urgent, accepted_offer_id, phone_revealed_to)
- [x] B9 QuoteOffer (price, unit, brand, message/notes; statuses pending/accepted/expired/declined)
- [x] B10 Notification (receiver `user_id` + type/payload; in-app messages, separate from push `DeviceToken`/`NotificationDelivery`)
- [x] B11 DeviceSubscription replaced by DeviceToken
- [x] B12 CategorySuggestion
- [x] B13 Advertisement/Ad (placement, starts_at, ends_at)
- [x] B14 ContactMessage
- [x] B15 Critical indexes (GIST + partial indexes)

## C. API endpoints (§4)

### Auth (§4.1) — [x] all five

### Catalog (§4.2)
- [x] GET /categories
- [x] GET /categories/{id}/subcategories
- [x] GET /businesses
- [x] GET /businesses/{slug} (approved reviews included)
- [x] GET /businesses/{id}/qr

### Business management (§4.3)
- [x] POST /businesses
- [x] PATCH /businesses/{id}
- [x] DELETE /businesses/{id}
- [x] POST /businesses/{id}/reviews
- [x] POST /reviews/{id}/reply

### Quote flow (§4.4) — paths differ from spec
- [x] POST /quotes/requests (+ legacy /quotes)
- [x] GET /quotes/requests/mine (offer counts + accepted business)
- [x] POST /quotes/requests/{id}/cancel (expires pending offers, notifies owners)
- [x] GET /quotes/requests/incoming?scope=new|archive|customers
- [x] POST /quotes/requests/{id}/decline (owner archive)
- [x] GET /quotes/{id} (customer/winner/admin-scoped offer detail)
- [x] POST /quotes/offers (+ legacy path; price/unit/brand/message)
- [x] PATCH /quotes/offers/{id}/accept (+ legacy path)
- [x] GET /admin/quotes + /stats + /{id}; POST /admin/quotes/{id}/cancel
- [x] GET /admin/analytics/overview + /quotes + /market

### Owner panel (§4.5)
- [x] GET /me/businesses
- [x] GET /me/businesses/{id}/analytics
- [x] GET /me/notifications (alias `/me/notifications` + `/notifications`, returns `unread_count`)
- [x] GET /me/notifications/unread-count (badge polling)
- [x] PATCH /me/notifications/read-all + PATCH /notifications/{id}/read
- [x] POST /notifications/subscribe replaced by `POST /devices`

### Admin (§4.6)
- [x] GET /admin/businesses?status=pending
- [x] PATCH /admin/businesses/{id}/approve|reject (both queue an in-app message to the owner; reject requires a reason)
- [x] POST /admin/notifications/broadcast (audience: all/owners/customers/single user; `notification.manage`)
- [x] PATCH /admin/businesses/{id}/toggle-24h
- [x] GET /admin/reviews?status=pending
- [x] review moderation via status PATCH + admin list
- [x] GET /admin/category-suggestions
- [x] POST /admin/categories (suggestion approval creates category/subcategory)
- [~] POST /admin/advertisements → `POST /ads`
- [x] GET /admin/stats/overview

### Utility (§4.7)
- [x] POST /uploads/image (5MB limit, ≤150KB JPEG compression)
- [x] POST /suggestions/categories
- [x] GET /health
- [x] GET /ready

## D. Complex logic (§5)

- [x] D1 Quote dispatch (multi-wave category/subcategory + radius ladder + night 24h preference + notifications + retry worker + lazy expiry + one-active-request guard)
- [x] D2 Rating aggregation on review approval
- [x] D3 Web push replaced by DeviceToken + LogPushProvider
- [x] D4 Iranian national ID validator
- [~] D5 Persian slug (currently ASCII + random suffix)
- [x] D6 User image pipeline: 5MB upload limit, filter/crop presets (`square` 800², `card` 640×360, `wide` 1200×600, `thumb` 200²), main JPEG ≤350KB, original max 1600px. Admin file-manager uploads stay raw.

## E. Frontend (§6)

- [x] /
- [x] /search
- [x] /businesses/{slug}
- [x] /categories
- [x] /quote/new (3-step form reusing the category sheet and map picker)
- [x] /quote/mine + /quote/mine/:id (list, offer comparison, accept, cancel)
- [x] /me/customers (owner tabs: new/archive/customers) and /me/quotes
- [x] /admin/quotes (stats, filters, detail modal, cancel)
- [x] /admin/analytics (general, quotes, market tabs)
- [x] /business/new → `/businesses/new` (5-step wizard: business, contact/address, optional data, services, preview)
- [x] /me + subroutes (`/me`, `/me/businesses`, `/me/notifications`, `/me/analytics`; `/owner` redirects)
- [x] /businesses/:id/edit (same wizard, prefilled; editing a rejected business resubmits it)
- [x] Business review form in a bottom sheet with star rating, optional text and a private-review checkbox; public reviews await admin approval
- [x] Business image upload compresses in-browser before upload (max 1600px, JPEG ~86%), while the backend always re-processes and generates named crops
- [x] Unread message badges on the header user icon and the profile notifications card; inbox supports mark-one/mark-all read and rejection edit links
- [x] Rejected business page shows a rejected badge, the rejection reason, and an owner-only «اصلاح و ارسال دوباره» action
- [x] /admin/notifications (announcement composer for all/owners/customers/single user)
- [x] admin businesses + reviews + quotes screens
- [~] /about, /contact, /rules (`/pages/:page` about+contact only)
- [x] TanStack Query (QueryClientProvider + `useApi`/`useMutation`/`useInfiniteQuery` across pages)
- [~] Zustand (auth + ui only; no quote store)
- [x] Neshan map (replaces OSM); draggable marker + address geocoding in the add-business location picker
- [x] Quote urgent/24h UX

## F–G. Env + seed
- [x] .env.example aligned with overrides
- [x] 18 categories, idempotent seed

## H. Tests (§10)

- [x] customer can create quote request
- [x] customer cannot have two active requests
- [x] urgent at night prefers 24h businesses and falls back to the parent category only when none exist
- [x] phone revealed only after acceptance
- [x] offer cannot be submitted for expired request
- [x] business owner can reply to review
- [x] admin can approve business (`test_admin_approves_business`)
- [x] rating_avg updates on review approval
- [x] OTP rate limit enforced (service + API tests)
- [~] Frontend Vitest ✅ (28 tests, ~92% on covered lib modules); Playwright ❌
- [~] Backend coverage 69% (target 80%; 147 tests passing)
- [x] Frontend coverage 60%+ (Vitest, lib modules)

## I. Deploy (§11)

- [x] Nginx+Certbot → Caddy (equivalent)
- [x] Daily backup script + systemd timer
- [x] Restore drill executed (categories=18, businesses=1)
- [x] Compose healthchecks (api/worker-exempt/web/caddy/db/redis)
- [x] Uptime Kuma + GlitchTip compose

## J. Definition of Done (§14)

- [x] All §4 endpoints implemented + tested (see `tests/test_endpoints_coverage.py`; documented path equivalents above)
- [~] §5 logic (rating + NID only)
- [x] 18 categories seeded
- [x] OTP SMS active (console; Mellipayamak KYC external)
- [x] Web push removed per session decision
- [~] HTTPS config only
- [x] Daily backup active + tested
- [x] GlitchTip compose stack
- [x] /docs
- [x] README local setup


## K. In-app messages and rejection UX (2026-10-28)

- [x] Rejection/approval create a `Notification` row with the owner as
  `user_id`; the row carries `business_id`, `rejection_reason` and an
  `action_url` to the edit wizard. Push delivery stays separate
  (`DeviceToken` / `NotificationDelivery`).
- [x] Unread count API + mark-one/mark-all read; the header user icon and the
  `/me` notifications card show a red unread badge.
- [x] Admin announcement composer supports all users, owners, customers or a
  single receiver, with an optional in-app destination link.
- [x] Public business detail still 404s for pending/rejected businesses, while
  the owner (and admins) can open the page and see status/reason.
- [x] Any owner edit on a rejected business clears the reason and moves it back
  to `pending` for admin review.
- [x] Tests: `backend/tests/test_notifications.py` (7 tests) — **126 backend
  tests passing**; frontend typecheck/build/Vitest passing.
- [x] Live verification on `localhost:8002` / `localhost:8080`: reject →
  message with reason → public 404 → owner rejected view → edit resubmits to
  pending → broadcast → unread count 2 → mark-all read → count 0.
- [x] Screenshots: [profile badges](docs/screenshots/messages-profile.png),
  [message inbox](docs/screenshots/messages-inbox.png),
  [rejected owner view](docs/screenshots/business-rejected-owner.png),
  [admin announcements](docs/screenshots/admin-announcements.png).

## L. Upload organization and image pipeline (2026-10-28)

- [x] User uploads are sharded as
  `uploads/businesses/{user_id}/{YYYY}/{MM}/{uuid}.jpg`; the local fallback now
  preserves nested directories and is served at `/uploads/*`.
- [x] Backend pipeline: EXIF orientation, optional filter (`none`, `warm`,
  `cool`, `vivid`, `mono`, `soft`), main crop (`square`, `card`, `wide`,
  `original`) with `center/top/bottom/left/right` anchor, JPEG compression, and
  `square` / `card` / `wide` / `thumb` variants. Main and matching crop share
  one stored object.
- [x] Business image upload accepts `crop`, `filter` and `anchor` form fields;
  admin `/admin/files/upload` bypasses processing and stores raw files.
- [x] Frontend best-effort compression before upload (15MB input guard, 5MB
  post-compression guard); failures fall back to the original file.
- [x] Tests: `backend/tests/test_image_processor.py`,
  `backend/tests/test_uploads.py`, storage prefix tests — **126 backend tests
  passing**; frontend Vitest 15 tests passing.
- [x] Live verification: uploaded a 2400×1600 JPEG, received an 800² main
  (51KB), `640×360`, `1200×600`, `200²` crops under the user/date prefix, S3
  object returned `image/jpeg`, and `/uploads/*` local serving was checked.


## M. Reviews, moderation and private feedback (2026-10-29)

- [x] Add-review form opens in a bottom sheet from the business page, with a
  compact five-star selector, optional text (max 300 chars), and a «نظر خصوصی»
  checkbox. Leaflet/map stacking no longer covers the sheet.
- [x] Public reviews start as `pending`; admin approval (`review.moderate`) or
  the business owner can make them public/declined, updating `rating_avg` /
  `rating_count` each time.
- [x] Private reviews are stored with `status=private` and `is_private=true`;
  they never appear in the public review list, rating aggregate, or the admin
  moderation queue, and the moderation endpoint rejects them.
- [x] Owners get `/me/reviews` with pending, private and approved reviews for
  their businesses, plus `/me/reviews/unread-count` and mark-seen. The profile
  has a «نظرات» card and the app header badge includes unseen reviews. Owners
  can approve/decline public reviews and reply to any review from this page.
- [x] Admin `/admin/reviews` lists all non-private reviews with search, business
  filter, approved/unapproved/rejected filters, pagination and approve/decline
  actions.
- [x] Migration `0018` recalculates every business rating from approved public
  reviews; demo seeding no longer writes fabricated rating values. Reviews show
  compact bundled stars instead of wide-spaced glyphs.
- [x] Duplicate reviews return `409 review_already_exists`; owners cannot review
  their own business.
- [x] Migration `0017_review_privacy` adds `reviews.is_private` and
  `reviews.owner_seen_at`.
- [x] Tests: `backend/tests/test_reviews.py` covers private visibility, owner
  inbox/badge, owner/admin moderation, admin filters+pagination, 300-char limit,
  approval/rejection rating recalculation, duplicates and self-review — **126
  backend tests passing**; Vitest 15 tests.
- [x] Live verification: private + public reviews created; public page showed
  none initially; owner inbox showed both with unread count 2; admin queue
  excluded the private one; approval published the public review and set the
  rating; header/profile badges and the bottom sheet were screenshot-verified.
- [x] Screenshots:
  [profile badge](docs/screenshots/reviews-profile-badge.png),
  [owner review inbox](docs/screenshots/reviews-owner-inbox.png),
  [public reviews](docs/screenshots/reviews-public-business.png),
  [add-review sheet](docs/screenshots/reviews-add-bottom-sheet.png),
  [admin review list](docs/screenshots/admin-reviews.png).


## N. Login redirects and compact admin dashboard (2026-10-29)

- [x] Clicking «ثبت نظر» while signed out opens an inline `LoginRequiredSheet`
  that explains a session is required; its «ورود / ثبت‌نام» action goes to
  `/login?next=<business-page>` and returns to the same business after OTP.
- [x] The review intent travels back in router state, so the review bottom sheet
  opens automatically after login; the URL stays clean (`/businesses/{slug}`)
  and refreshing does not reopen the sheet.
- [x] Shared redirect helpers (`frontend/src/lib/auth-redirect.ts`) only accept
  same-origin in-app paths, reject external/protocol-relative/backslash URLs and
  login loops, and preserve path, query string and hash.
- [x] `LoginPage` honours `?next=`, shows a “you will return” hint, and guards
  against a stale `<Navigate>` race after OTP verification.
- [x] Auth guards preserve the attempted destination for `/me/*`, `/admin/*`,
  `/quote/new`, `/quote/mine`, `/businesses/new` and `/businesses/:id/edit`
  through the reusable `RequireAuth` component / location-aware layout guards.
- [x] Saving a business uses the same login prompt and return path; the header
  account icon still lands on the role-appropriate home after login.
- [x] Admin dashboard density pass: sidebar 256→240px, header 64→56px, main
  padding 32/20→24/16px, scoped typography (sm 13px, xs 11px, headings down
  ~1px), inputs/buttons 48→40px, and table rows 12/16px→10/12px. Customer-facing
  screens keep their larger tap targets.
- [x] Tests: frontend Vitest **15 tests passing** (added redirect / intent
  utility coverage); typecheck and production build pass. Backend remains
  **126 tests passing**.
- [x] Browser E2E at 1440×900: logged-out prompt → OTP login → automatic return
  to `/businesses/nakhl-hotel` with the review form open and a clean URL;
  `/me/reviews?page=2` redirects to
  `/login?next=%2Fme%2Freviews%3Fpage%3D2`; admin dashboard, reviews and
  businesses screens were checked after the density changes.
- [x] Screenshots:
  [login-required prompt](docs/screenshots/login-required-review.png),
  [review form after login](docs/screenshots/review-after-login.png),
  [compact dashboard](docs/screenshots/admin-compact-dashboard.png),
  [compact reviews](docs/screenshots/admin-compact-reviews.png),
  [compact businesses](docs/screenshots/admin-compact-businesses.png).


## O. Full quote ecosystem (2026-10-31)

- [x] Customer 3-step request form (`/quote/new`): service/item + reusable
  category/subcategory bottom sheet, address/neighborhood + reusable Neshan map
  picker, optional urgent toggle (2-hour deadline) and supplementary notes.
  The form validates each step, hides the mobile app nav, keeps the action bar
  pinned, and handles the `active_quote_exists` conflict with a link to the
  current request.
- [x] Customer quote inbox (`/quote/mine`, also `/me/quotes`): live countdown,
  offer count, address/category, waiting state, current request card, and a
  collapsible history for accepted/cancelled/expired requests. The bottom nav
  now marks the quote section active.
- [x] Customer quote detail (`/quote/mine/:id`): compares offers by business,
  rating, price, unit, brand and message; selecting an offer requires
  confirmation, reveals only that business's phone, expires competing offers and
  sends the owner an in-app message. Cancelling a request expires pending offers
  and notifies their owners.
- [x] Owner workspace (`/me/customers`): three tabs — new received requests,
  accepted customers, and archive. New requests support decline or a bottom-sheet
  offer form (price, unit, brand, message, business picker when the owner has
  multiple matching businesses). Archive tracks sent/declined/lost offers;
  accepted customers expose the customer phone and a call action.
- [x] Offer/request API enrichment: category/subcategory refs, customer display
  name (phone only on the winners tab), offer counts, accepted business/contact,
  matching businesses and the owner's own offer. Owner list/detail responses
  never include a customer phone before acceptance.
- [x] Authorization: quote detail is limited to the customer, admins with
  `quote.read`, or an owner with an offer on that request; declined offers are
  hidden from customers; duplicate offers/declines return 409.
- [x] Admin quote dashboard (`/admin/quotes`, permission `quote.read`): totals,
  active/urgent, accepted, acceptance rate, offers/pending offers; filters,
  search, paginated table, request/offer detail modal, and cancel action gated by
  `quote.manage` with an audit-log entry and owner notifications.
- [x] Migration `0019` adds `offers.unit` plus quote status/created indexes.
- [x] Notifications: quote request, new offer, accepted offer and cancellation
  create typed in-app messages with links to the relevant quote/customer page.
- [x] Tests: `backend/tests/test_quote_flow.py` covers customer/owner payloads,
  phone privacy, counts, scopes, duplicate/decline, cancellation, expiry,
  unrelated-owner access, admin stats/list/detail/cancel and geo/24h dispatch —
  **135 backend tests passing**. Frontend Vitest **24 tests passing**; typecheck
  and production build pass.
- [x] Browser E2E (390×1000): submitted a new request through all 3 steps,
  received it in the owner «جدید» tab, submitted an offer with unit/brand/message,
  saw it move to archive, accepted it as the customer, verified the owner phone
  appearing under «مشتریان» and the accepted business contact for the customer.
  Admin dashboard checked at 1440×900 with zero console errors.
- [x] Screenshots:
  [customer list](docs/screenshots/quote-customer-list.png),
  [customer offer detail](docs/screenshots/quote-customer-detail.png),
  [accepted customer request](docs/screenshots/quote-customer-accepted.png),
  [owner new requests](docs/screenshots/quote-owner-new.png),
  [owner accepted customers](docs/screenshots/quote-owner-customers.png),
  [owner archive](docs/screenshots/quote-owner-archive.png),
  [offer sheet](docs/screenshots/quote-owner-offer-sheet.png),
  [form step 1](docs/screenshots/quote-form-step1.png),
  [form step 2](docs/screenshots/quote-form-step2.png),
  [form step 3](docs/screenshots/quote-form-step3.png),
  [admin quote dashboard](docs/screenshots/admin-quotes.png).


## P. Analytics dashboard and demand tracking (2026-10-31)

- [x] New `/admin/analytics` admin page with three tabs (`?tab=general|quotes|market`),
  gated by `stats.read`, added to the sidebar and the main dashboard cards.
- [x] **General tab**: widgets for businesses (total/approved), reviews, quotes,
  searches, users and actionable pending counts; a 14-day multi-series line
  chart for searches, quote requests, quote responses and registrations; a
  grouped bar chart comparing the quote funnel (requests → sent → seen →
  responded → chosen) for today / this week / this month / all time; a 24-hour
  today bar chart for searches and quote requests; a role-composition donut with
  flag labels; and a pending-action chart.
- [x] **Quotes tab**: widgets for total/active/accepted quotes, offers, response
  rate, average first offer and average choice time; status pie (active,
  accepted, cancelled, expired); timing bars for request → sent / seen / first
  offer / customer choice; and funnel conversion details.
- [x] **Market tab**: demand-vs-supply bars for the top categories; full category
  table (businesses, searches, no-result searches, quotes, active unanswered
  quotes, demand and a verbose status such as «جذب فوری»، «کمبود عرضه»،
  «متعادل»، «عرضه مازاد»، «بدون تقاضا»); most-wanted subcategories table;
  top keywords with search/avg-results/no-result counts; and top no-result
  keywords with related category.
- [x] Search instrumentation: `GET /businesses` logs first-page search events in
  `search_logs` with query, normalized query, inferred category/subcategory,
  result count and timestamp. Cursor pagination is not logged, so loading more
  results does not inflate demand.
- [x] Quote instrumentation: `quote_deliveries` records every dispatched
  quote/business pair and `seen_at` is set when the owner inbox renders the new
  request. `quote_requests.accepted_at` records the customer's choice. This
  enables the sent → seen → response → choice funnel and timing metrics.
- [x] New endpoints `GET /admin/analytics/overview`, `/quotes`, `/market`
  (`stats.read`); all analytics timestamps are grouped in `Asia/Tehran`, with
  calendar week starting Saturday and month-to-date ranges.
- [x] Migration `0020` adds `search_logs`, `quote_deliveries`, and
  `quote_requests.accepted_at` (backfilled from accepted offers). Search and
  delivery tables are exposed in the superadmin data browser.
- [x] Tests: new `backend/tests/test_analytics.py` covers search logging, quote
  delivery/seen tracking, accepted_at, daily/hourly series, funnel ranges, role
  counts, quote status/timing metrics, market statuses, keyword tables, empty
  payloads and permission denial — **147 backend tests passing**. Frontend
  analytics helpers bring Vitest to **28 tests**; typecheck/build pass.
- [x] Browser verification at 1440×900 and 1280/1024 widths: all three tabs
  render with zero console errors and no document-level horizontal overflow;
  charts/tables were checked against the seeded analytics dataset.
- [x] Screenshots:
  [general dashboard](docs/screenshots/analytics-general.png),
  [general lower charts](docs/screenshots/analytics-general-bottom.png),
  [quote analytics](docs/screenshots/analytics-quotes.png),
  [market demand chart](docs/screenshots/analytics-market.png),
  [category demand table](docs/screenshots/analytics-market-table.png),
  [keyword tables](docs/screenshots/analytics-market-keywords.png).


## Q. Analytics follow-up: business performance, market map, event logs (2026-10-31)

- [x] Added three tabs to `/admin/analytics`:
  - **کسب‌وکارها** — sortable performance table.
  - **نقشه** — full-height Neshan market map.
  - **لاگ رویدادها** — event volume/donut charts plus a paginated raw log.
- [x] Business performance endpoint `GET /admin/analytics/businesses` returns
  category/subcategory, views, offered/accepted quote counts, response rate,
  rating, negative-review rate and a verbose operational status. The table is
  sortable client-side on every column (including response, rating, negative
  rate and status) and has a local search field.
- [x] Response-rate bars and negative-rate bars are rendered as visual
  indicators. Status labels cover «عملکرد عالی»، «متعادل»، «کم‌پاسخ»،
  «نیازمند بررسی» and «بحرانی — نظرات منفی».
- [x] Map endpoint `GET /admin/analytics/map` returns approved businesses with
  coordinates, active normal quotes and active urgent quotes. The map uses
  three pin colors (green/sky/red), layer toggles with counts, popups, a fixed
  city-centred initial view, and a large full-content viewport height.
- [x] Event log endpoint `GET /admin/analytics/logs` derives a paginated raw
  stream from searches, user registrations, business creation, reviews, quote
  requests, offers, owner views and customer choices. Supports type filtering,
  page/per-page, and a consistent `{data, meta}` envelope.
- [x] `GET /admin/analytics/logs/summary` provides total event counts by type
  and a 14-day daily volume series for the line/donut visualisations.
- [x] All new endpoints use `stats.read`; the analytics page is lazy-loaded to
  keep the main customer bundle below the 500kB warning threshold.
- [x] Tests: analytics endpoints now cover business performance, map data,
  logs pagination/filtering and summary aggregation — **147 backend tests
  passing**; frontend Vitest 28 tests, typecheck and build pass.
- [x] Browser checks: business table sorting verified (response-rate header
  click changed the first row), map loaded 24 tiles with 21 colored pins, logs
  tab rendered 25 paginated rows with zero console errors.
- [x] Screenshots:
  [business performance](docs/screenshots/analytics-businesses.png),
  [market map](docs/screenshots/analytics-map.png),
  [event logs](docs/screenshots/analytics-logs.png),
  [raw event table](docs/screenshots/analytics-logs-table.png).

## R. Quote dispatch reliability, retry worker and manual assignment (2026-10-31)

- [x] Root cause removed: dispatch hours are evaluated in `Asia/Tehran` rather
  than UTC, so a request created at 09:00 local is no longer treated as outside
  the 06–21 window.
- [x] Root cause removed: a missing exact subcategory no longer drops the
  request. The candidate ladder tries exact subcategory + tight radius, parent
  category + tight radius, expanded radius, then category-wide fallback.
- [x] Requests are dispatched as waves to unique owners (one business per owner
  per quote) with configurable initial/retry batch sizes, minimum target and
  maximum rounds. Already-contacted owners are never repeated.
- [x] Silent waves expand automatically. Seen-without-offer expansion is a
  dashboard toggle. A wave with a pending offer stops auto-expansion. If no
  approved candidate exists yet, the request stays `searching` and is rescanned
  without burning a delivery round.
- [x] `quote_requests` now stores `dispatch_round`, `dispatch_status`,
  `last_dispatched_at`, `next_dispatch_at`; `quote_deliveries` stores `round`,
  `source` and `responded_at`; `quote_dispatch_runs` audits every wave
  (candidate count, delivery count, trigger and fallback detail).
- [x] Redis Streams + delayed sorted-set broker wakes the worker, while the
  worker also reconciles due `next_dispatch_at` rows from Postgres. A lost Redis
  message or restart cannot strand an active quote. Locking is done on request
  ids to avoid Postgres outer-join `FOR UPDATE` errors.
- [x] `/admin/settings?tab=dispatch` edits strategy values: enable/disable,
  batch sizes, min target, max rounds, normal/urgent response windows,
  seen-without-offer expansion, tight/expanded radius, category and
  outside-radius fallbacks, Tehran sending window, night-urgent policy and
  no-candidate rescan interval.
- [x] `GET /admin/quotes/{id}/dispatch` returns the wave summary, delivery
  audit (owner, seen/offer status, source/round) and recent runs.
  `POST /admin/quotes/{id}/assign` manually adds approved businesses/owners with
  audit logging and de-duplication. `POST /admin/quotes/{id}/dispatch-now`
  forces the next wave for `quote.manage`.
- [x] `/admin/settings?tab=dispatch` includes a Persian «راهنمای ارسال استعلام»
  modal: one-screen overview, visual flow from request to retry/end, five
  decision rules, a variable glossary mapped to the settings labels and a timed
  example. The guide opens from the settings header and works on mobile.
- [x] Customer quote list/detail includes a compact dispatch graph: ثبت → ارسال
  → مشاهده → پیشنهاد, counts, current wave/max, next wave countdown and reasons
  for scheduled/searching/waiting/reviewing/offers/exhausted states. Owner names
  are never exposed to the customer.
- [x] Fallback-delivered owners can see and answer the request even when the
  subcategory/radius differs; only actual deliveries are marked seen.
- [x] Migration `0021` adds the dispatch columns/audit table, backfills delivered
  waves, marks closed requests complete, and schedules previously dropped active
  requests for immediate worker recovery.
- [x] Tests: new `backend/tests/test_quote_dispatch.py` covers Tehran quiet
  hours, subcategory fallback visibility/offer, urgent-night fallback, multi-wave
  expansion and max rounds, seen-without-offer toggle, no-candidate recovery,
  worker reconciliation, manual assignment/idempotency and settings validation.
  **147 backend tests** and **28 frontend Vitest tests** pass; typecheck and
  production build pass.
- [x] Browser verification: owner inbox receives the request and marks it seen;
  customer graph shows 3 delivered / 1 seen / next wave; admin dispatch modal
  shows auto + manual deliveries; strategy form loads and saves.
- [x] Screenshots:
  [dispatch strategy settings](docs/screenshots/admin-settings-dispatch.png),
  [admin dispatch waves and manual assignment](docs/screenshots/admin-quote-dispatch.png),
  [customer dispatch status graph](docs/screenshots/quote-dispatch-status.png),
  [mobile dispatch status graph](docs/screenshots/quote-dispatch-status-mobile.png),
  [dispatch help — overview](docs/screenshots/admin-dispatch-help.png),
  [dispatch help — variables](docs/screenshots/admin-dispatch-help-variables.png),
  [dispatch help — mobile](docs/screenshots/admin-dispatch-help-mobile.png).

## S. UX polish, category search, business gallery and desktop navigation (2026-10-31)

- [x] Category/subcategory picker has an inline search field. It filters both
  levels locally with Persian/Arabic character normalisation (`ي/ى→ی`, `ك→ک`,
  ZWNJ/space collapse), shows category and subcategory matches together, and
  loads the compact catalog once from `GET /categories/subcategories` so typing
  does not issue a database request per keystroke.
- [x] Business gallery: up to six images per business (`MAX_BUSINESS_IMAGES`, default 6, configured in `.env`). `business_images` stores
  URL, sort order and `is_main`; `businesses.profile_image_url` mirrors the
  chosen main image for cards/search. Migration `0022` creates the table and
  backfills every existing cover photo.
- [x] Add/edit business photo UI: multi-file picker, processing/uploading state,
  preview grid, remove action, explicit «تعیین به‌عنوان اصلی» action and a
  starred main badge. Create/update payloads send the ordered gallery plus the
  main URL; the public detail page presents the gallery as a carousel with a
  full-screen lightbox (see §T).
- [x] Search autofocus is reliable on cold load and mobile viewports, a clear
  button empties the field, and typing is debounced for 450ms after the last
  keystroke. A live browser check typed `مکانیک` character-by-character and
  confirmed exactly one `/businesses` request.
- [x] The add/edit-business and quote wizards now show a close (×) icon instead
  of a back arrow. Closing uses a replace navigation to `/me/businesses` or
  `/quote/mine`, so browser Back does not re-enter a half-completed wizard.
- [x] Both wizard content areas have extra bottom clearance (`pb-24`) so the
  sticky action bar cannot cover the last fields.
- [x] Clicking a business pin in search map mode opens a sticky bottom card
  with the business card and a detail hint. Marker callbacks are opt-in through
  `NeshanMap.onMarkerClick`, while maps without the callback keep popups.
- [x] Desktop header navigation: Home, Categories, Search and Quotes appear as
  centered nav links at `md+`; the mobile bottom toolbar remains unchanged.
  Vendor chunk splitting keeps the main JS bundle at ~299kB (below the 500kB
  warning threshold).
- [x] `MAX_BUSINESS_IMAGES` is configurable in `.env`, `backend/.env`,
  `.env.prod.example` and both compose files; `/me/businesses` returns
  `max_images` and the wizard uses it instead of a hardcoded UI limit.
- [x] Tests: **149 backend tests** pass (new gallery create/edit/public tests,
  max-six validation and picker catalog coverage). Frontend **28 Vitest tests**,
  typecheck and production build pass; migration `0022` applied live.
- [x] Browser verification at 1440×1000 and 390×844: header nav, autofocus,
  debounce, category search results, six-photo 3×2 editor, public gallery, map pin
  bottom card and close-form routing all verified with zero console errors.
- [x] Screenshots:
  [desktop header navigation and search](docs/screenshots/search-desktop-header.png),
  [category picker inline search](docs/screenshots/category-picker-search.png),
  [cross-level category search results](docs/screenshots/category-picker-search-results.png),
  [six-photo 3×2 editor](docs/screenshots/business-gallery-editor.png),
  [public business gallery](docs/screenshots/business-gallery-detail.png),
  [map pin bottom card](docs/screenshots/map-business-sheet.png),
  [form close icon](docs/screenshots/form-close-header.png).

## T. Business detail redesign — hero, gallery carousel, owner and actions (2026-10-31)

- [x] Public business detail has a cleaner card-based hero: the gallery is the
  visual lead, followed by category, name, rating, verification/24h chips and
  the short description. The old local “جزئیات کسب‌وکار” header was removed so
  the global back action and gallery remain the focus.
- [x] Multi-image businesses render a swipeable, arrow-and-dot carousel with an
  image counter. Clicking any slide opens a full-screen dark lightbox with
  keyboard (Esc / ← / →), arrow, thumbnail and swipe navigation. Body scroll is
  locked while open and restored on close.
- [x] Businesses with one image still open the lightbox; businesses without
  images get a quiet branded placeholder instead of a broken media gap.
- [x] Contact actions were rebuilt as two clear buttons: a primary call button
  (business phone, falling back to the owner phone) and a secondary Neshan
  directions button. Save is a compact bookmark control over the hero.
- [x] The owner is exposed by `GET /businesses/{slug}` as
  `owner: {name, phone}`, and the detail page shows a dedicated owner card with
  an avatar initial, name and tap-to-call phone chip. The owner edit shortcut
  remains available to the business owner.
- [x] The about card now holds the full description, address and Instagram
  link; reviews and the map keep their existing behavior.
- [x] Tests: **149 backend tests** pass, including the owner payload assertion;
  frontend **28 Vitest tests**, typecheck and production build pass.
- [x] Browser verification at 390×844 and 1440×1000 covered six-slide carousel
  state, lightbox open/close and next navigation, scroll lock restoration,
  owner name/phone, call links, and zero console errors / horizontal overflow.
- [x] Screenshots:
  [business detail hero](docs/screenshots/business-detail-hero.png),
  [gallery lightbox](docs/screenshots/business-gallery-lightbox.png),
  [lightbox second image](docs/screenshots/business-gallery-lightbox-slide.png),
  [carousel second slide](docs/screenshots/business-detail-gallery-slide.png),
  [actions and owner card](docs/screenshots/business-detail-actions-owner.png),
  [desktop business detail](docs/screenshots/business-detail-desktop.png).
