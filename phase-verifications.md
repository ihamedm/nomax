# NOMAX — implementation verification checklist

Source of truth: `proposal.md` (original v1) with overrides from `session.md` and
`docs/adr/*` (no web push, superadmin, Neshan, Mellipayamak, outbox).
Status: `[x]` verified implemented, `[~]` partial, `[ ]` missing / to verify.

## A. Non-negotiable business rules (§2)

- [x] A1 Anonymous quote: customer phone hidden until offer acceptance
- [x] A2 Phone revealed only to accepted business (`phone_revealed_to`)
- [x] A3 One active quote request per user (DB partial unique)
- [x] A4 Dispatch window: normal 06–21; urgent at night only `is_24h`
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
- [x] B9 QuoteOffer (brand + notes/message)
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
- [x] GET /quotes/requests/mine (`test_my_quotes_lists_only_own_requests`)
- [x] POST /quotes/requests/{id}/cancel
- [x] GET /quotes/requests/incoming
- [x] POST /quotes/offers (+ legacy path)
- [x] PATCH /quotes/offers/{id}/accept (+ legacy path)

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

- [x] D1 Quote dispatch (category/subcat + 10km + night 24h + notifications + expiry)
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
- [x] /quote/new
- [x] /quote/mine
- [x] /business/new → `/businesses/new` (5-step wizard: business, contact/address, optional data, services, preview)
- [x] /me + subroutes (`/me`, `/me/businesses`, `/me/notifications`, `/me/analytics`; `/owner` redirects)
- [x] /businesses/:id/edit (same wizard, prefilled; editing a rejected business resubmits it)
- [x] Business review form in a bottom sheet with star rating, optional text and a private-review checkbox; public reviews await admin approval
- [x] Business image upload compresses in-browser before upload (max 1600px, JPEG ~86%), while the backend always re-processes and generates named crops
- [x] Unread message badges on the header user icon and the profile notifications card; inbox supports mark-one/mark-all read and rejection edit links
- [x] Rejected business page shows a rejected badge, the rejection reason, and an owner-only «اصلاح و ارسال دوباره» action
- [x] /admin/notifications (announcement composer for all/owners/customers/single user)
- [x] admin businesses + reviews screens
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
- [x] urgent only dispatched to 24h businesses at night
- [x] phone revealed only after acceptance
- [x] offer cannot be submitted for expired request
- [x] business owner can reply to review
- [x] admin can approve business (`test_admin_approves_business`)
- [x] rating_avg updates on review approval
- [x] OTP rate limit enforced (service + API tests)
- [~] Frontend Vitest ✅ (15 tests, ~92% on covered lib modules); Playwright ❌
- [~] Backend coverage 69% (target 80%; 126 tests passing)
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
