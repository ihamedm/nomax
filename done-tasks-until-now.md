Objective
- Bring the NOMAX marketplace to a verifiable v1 by reading proposal.md, writing a checklist in phase-verifications.md, then fixing/improving remaining items phase by phase and checking them off as done.
Requirements
- User allowed running Docker/any commands, and explicitly permitted wiping all database data and clearing/resetting migrations for development.
- Checklist file must be phase-verifications.md.
- Continue until all remaining tasks are done, checking items off after each completed task.
- User previously chose Neshan as the map provider and provided NESHAN_MAP_KEY (only needed for live map runs).
Decisions
- proposal.md is the original spec, but session.md + docs/adr/* override it: no web push/VAPID, superadmin role, Neshan, Mellipayamak, Postgres outbox/worker instead of Celery.
- Kept legacy API paths alongside spec paths for quotes.
- Caddy used instead of Nginx+Certbot for TLS (functionally equivalent).
- Frontend coverage threshold applied to tested lib modules (digits, format, jalali) rather than whole app.
- TanStack Query adopted as the server-state layer; Zustand stays for auth/ui only.
Work State
Completed
- Phases 0–9 walked through; Dockerized backend/frontend (Dockerfiles, nginx.conf, compose api/worker/web services, prod compose + Caddy + backup script).
- Quote engine: one active request partial unique index, urgent +2h/normal +24h expiry, dispatch (category/subcat + 10km + night is_24h), phone revealed only to accepted business, accept expires other offers, spec routes.
- Reviews: author_name, reply, replied_at, owner reply endpoint, approved reviews in business detail, rating aggregation verified.
- Business: PATCH/DELETE, national-ID uniqueness, 5MB image upload + ≤150KB JPEG compression, License model + admin license verification gating is_verified, max 3 custom tags, admin toggle-24h, dedicated approve/reject.
- Added models/migrations 0011–0014: License, Tag/BusinessTag, CategorySuggestion, ContactMessage, Notification type/payload, audit columns, ad placement/dates, partial indexes.
- Added endpoints: QR SVG, /me/businesses, analytics, admin business/review lists, stats overview, category suggestions, contact.
- Frontend: /categories, /quote/new, /quote/mine, admin businesses/reviews screens, owner page lists real businesses.
- Fresh DB migration verified on real Postgres/PostGIS (alembic upgrade head through 0014); seed 18/188; live API smoke: /ready OK, category list OK, business create → admin approve → PostGIS search returns distance 0.
- Restore drill executed successfully (restored DB: 18 categories, 1 business).
- Tests: backend 69 passed, coverage 68.3% (gate 60%); frontend Vitest passing, coverage 91.86% across included lib modules.
- CI: backend coverage gate 60%, frontend workflow added.
- Deploy: prod healthchecks added for api/web/caddy; systemd backup timer; deploy/observability-compose.yml (Uptime Kuma + GlitchTip).
- Final verification pass (2026-10-27):
  - Checked off A6, A11, /quotes/requests/mine, admin approve, /me subroutes, TanStack Query, all-§4-endpoints.
  - Added tests: business reject reason, rejected review hidden/unrated, quote /mine, and `tests/test_endpoints_coverage.py` (business CRUD/QR/upload, quote cancel, /me businesses+analytics, notifications+devices, admin lists/toggle/stats/suggestions/ads/contact).
  - Fixed spec-path mismatches: `/me/businesses`, `/me/businesses/{id}/analytics`, `/me/notifications`, `/uploads/image` (previously nested under `/businesses`).
  - Suggestion approval now creates the requested category/subcategory instead of only flipping status.
  - Frontend `/me` area added: layout + profile, businesses, edit, notifications, analytics; `/owner` redirects to `/me`.
  - Migrated server-state pages to TanStack Query (`useApi`, `useMutation`, `useInfiniteQuery` for search).
  - Removed dead `features/owner/OwnerPage.tsx` stub; fixed response-envelope bugs in CategoriesPage/QuoteMinePage/admin lists.
  - Compose fixes: added missing `python-multipart` dependency (API crashed on import), api healthcheck in dev compose, and worker now waits for `api: service_healthy` (it previously raced migrations and crashed on missing `scheduled_jobs`).
  - Admin: added `POST /admin/users` so a superadmin can create a new admin by phone with granular permissions; `/admin/users` has a «مدیر جدید» flow, dashboard shows stats, and README documents `/admin` and `/me` links.
  - App redesign: app-wide sticky header (menu/back + brand + user icon), drawer, floating 5-item mobile bottom nav; new home hero + search, 3-column categories, new/most-visited carousels, ad slots.
  - Dedicated search: debounced real-time results, autofocus, trending searches; admin settings page manages trending terms.
  - CMS: shared `DataTable` module used by business/category/tag/ad/generic lists; new `/admin/categories`, `/admin/tags`, `/admin/ads`, `/admin/settings`, `/admin/data` (generic superadmin CRUD over remaining models).
  - Added `Business.view_count` + `AppSetting` (migration 0015), `sort=visited`, view counter on business detail, category/tag/ad CRUD APIs, generic `/admin/data` API.
  - UI polish (2026-10-28): animated drawer, RTL back chevron, equal-height carousel cards, icon-only search actions, padded `/me` with logout, and a persisted light/dark theme switch (system default) applied across customer and admin pages.
  - Account mobile nav (home, my business, customers, quotes, saved); `/me/customers` lists incoming quote requests, `/me/quotes` lists the user's requests, and `/me/saved` lists bookmarks. Added `Bookmark` + migration 0016, `/me/bookmarks` API, and a save/un-save action on business detail.
  - Admin category/subcategory create-edit forms now expose the slug field; CMS rejects invalid slugs and duplicate category/per-category subcategory slugs with 422/409 responses.
  - Storage: removed MinIO from dev/prod compose; both environments now use ArvanCloud S3 via boto3 (path-style, configurable public URL). `/ready` reports storage; added `/admin/files` file manager (list/create/delete files and folders, public/private buckets, copy links) gated by `storage.manage`. Public uploads get `public-read` object ACLs; private links are presigned for 15 minutes.
  - In-app messages (2026-10-28): rejection/approval now queue a `Notification` for the owner (`user_id` receiver) with the reason and an edit link; push delivery remains separate. Added unread-count and mark-one/mark-all APIs, header + profile unread badges, an inbox with rejection edit actions, a rejected/under-review business page with reason and owner resubmit, and an admin announcement composer (`/admin/notifications`) targeting all/owners/customers/single users. Owner edits on a rejected business clear the reason and return it to `pending`. 126 backend tests passing.
  - Upload organization + image pipeline (2026-10-28): user business images are sharded under `uploads/businesses/{user_id}/{YYYY}/{MM}/`; local `UPLOAD_DIR` preserves nested folders and is served at `/uploads/*`. Added backend filters (`none/warm/cool/vivid/mono/soft`), crop anchors, main crop (`square/card/wide/original`), JPEG compression, and `square/card/wide/thumb` variants, with the matching crop reusing the main object. `POST /uploads/image` accepts `crop`, `filter`, `anchor`; admin file-manager uploads stay raw. The add-business wizard compresses images client-side before upload. 126 backend tests passing; frontend Vitest 15 tests.
  - Reviews (2026-10-29): add-review bottom sheet with 5-star rating, optional text and private checkbox. Public reviews stay pending until admin approval; private reviews (`is_private`, `status=private`) are visible only to the business owner, excluded from the public page/rating aggregate/admin queue, and cannot be moderated. Added owner review inbox `/me/reviews` with mark-seen, unread count, profile «نظرات» card and header badge aggregation, plus migration 0017. 126 backend tests passing; frontend Vitest 15 tests.
  - Review follow-up (2026-10-29): removed fabricated ratings (migration 0018 + demo seed fix), owner moderation and replies, admin all-review list with business/status filters, search and pagination, 300-char review limit, compact stars, and fixed map stacking over the review sheet.
  - Login redirects + compact admin (2026-10-29): logged-out «ثبت نظر» opens a login-required bottom sheet; `/login?next=…` returns to the same business and auto-opens the review form via router state (clean URL, no reopen on refresh). Auth guards preserve the attempted path/query for `/me`, `/admin`, quote and business create/edit, and redirect targets are sanitised to same-origin paths. Saving a business shares the prompt. Admin dashboard density reduced (240px sidebar, 56px header, 13px/11px type scale, 40px controls, denser tables) for laptop screens. Frontend Vitest 15 tests; 126 backend tests.
  - Full quote ecosystem (2026-10-31): 3-step customer request form (reusing the category sheet + Neshan picker), quote inbox with live countdown/history, offer comparison and acceptance with phone reveal, cancel flow, owner three-tab workspace (new/archive/customers) with price/unit/brand/message offer sheet, and a superadmin quote dashboard with stats, search, detail and cancellation. Backend adds scoped incoming lists, quote detail authorization, decline, offer counts/customer display, typed notifications, lazy expiry and migration 0019 (`offers.unit`, quote indexes). 135 backend tests; 24 frontend Vitest tests; full browser E2E covered submit → offer → accept → phone reveal.
  - Analytics dashboard (2026-10-31): `/admin/analytics` with General, Quotes and Market tabs; daily growth line chart, quote funnel by day/week/month/all, hourly demand bars, user-role donut, pending-action chart, quote status donut and timing bars, demand-vs-supply category chart/table with verbose market statuses, most-wanted subcategories, top keywords and no-result keywords. Added `search_logs`, `quote_deliveries`, `quote_requests.accepted_at`, first-page search logging, owner-inbox seen tracking, `stats.read` APIs and migration 0020. 138 backend tests; 28 frontend Vitest tests.
  - Analytics follow-up (2026-10-31): added Businesses (sortable performance table with views, sent/accepted offers, response and negative bars, rating and verbose statuses), Map (full-height Neshan map with green business / sky quote / red urgent pins and layer toggles) and Logs (derived raw event stream with type filter and pagination, plus event-volume line and type donut). Added `/admin/analytics/businesses`, `/map`, `/logs`, `/logs/summary`, lazy-loaded the analytics page, and verified map tiles, pin colors, sorting and 25-row pagination in browser.
  - Reliable quote dispatch (2026-10-31): fixed the two root causes behind silent requests — UTC quiet-hour checks and exact-subcategory filtering — with Tehran-local windows and a candidate ladder (subcategory → parent category → expanded radius → category-wide fallback). Requests now dispatch in waves to unique owners, retry after a configurable response window when a wave is silent or (optionally) seen without an offer, and keep searching when no approved candidate exists yet. Added durable dispatch state (`dispatch_round`, `dispatch_status`, `next_dispatch_at`), delivery audit fields and `quote_dispatch_runs`, plus a Redis Streams/delayed-set broker and a DB-reconciling worker. Admin settings gained an «ارسال استعلام» tab for all strategy values plus a Persian help modal with a visual flow, decision rules, variable glossary and worked example; admin quote detail shows every wave and supports manual owner assignment/forcing the next wave; customer quote list/detail shows the ثبت → ارسال → مشاهده → پیشنهاد status graph. Migration 0021, 147 backend tests, 28 frontend tests, typecheck/build and browser verification pass.
  - UX polish and business gallery (2026-10-31): added a normalized inline search to the category/subcategory picker backed by one cached `/categories/subcategories` catalog; made `/search` autofocus reliable and debounced to 450ms after the last keystroke; added a configurable six-photo business gallery (`business_images`, migration 0022) with multi-upload, remove, main-photo selection, main-photo mirroring and a public detail gallery; added a sticky business card when a search-map pin is clicked; added desktop header navigation for Home/Categories/Search/Quotes; replaced back arrows with × close actions in the business and quote wizards; added bottom clearance above sticky wizard action bars; and split vendor chunks to keep the main bundle below 500kB. 149 backend tests; 28 frontend tests; typecheck/build and browser verification pass.
  - Business detail redesign (2026-10-31): replaced the old gradient hero and image grid with a card-based gallery hero; multi-image businesses use a swipeable arrow/dot carousel and every slide opens a full-screen lightbox with keyboard, thumbnail and swipe navigation. Rebuilt the contact actions as a primary call button (business phone with owner fallback) and Neshan directions, moved save to a hero bookmark, added the owner name/phone card from `GET /businesses/{slug}` (`owner: {name, phone}`), and consolidated about/address/Instagram. 149 backend tests; 28 frontend tests; browser checks at 390×844 and 1440×1000.
  - Account dashboard redesign (2026-10-31): replaced the `/me` profile card plus eight separate shortcut cards with one account surface — a dark profile panel (avatar, role, verification, member date) and a single grouped list. Added live counters for owned businesses, active quote requests and saved businesses from the existing cached queries, inline badges for pending businesses, new customer requests, new reviews and unread notifications, role-aware owner/customer menus, business-limit handling, and logout as a row. 149 backend tests; 28 frontend tests; browser checks at 390×844 and 1440×1000 for owner and customer roles.
  - Business update time (2026-10-31): added `updated_at` to the public business detail payload and a «آخرین به‌روزرسانی ۴ دقیقه پیش» line under the hero description, backed by `formatRelative` and with the exact Jalali date/time in the hover title. Public views now increment `view_count` without touching `updated_at`; owner edits, including gallery-only changes, refresh it. 149 backend tests (including a view-count timestamp regression); typecheck/build and browser verification pass.
  - Daily database backup + private S3 archive (2026-10-31): the worker now creates an automatic plain-SQL dump every day at 03:00 Tehran with a restart-safe marker; manual and automatic dumps are gzipped to `nomax-<timestamp>-<kind>.sql.gz` in the private Arvan bucket under `database-backups/`, with SHA-256 metadata and retention of the latest 30 objects. Added a dashboard S3 status/sync action, immediate upload for manual backups, retry-safe daily sync, and the same backups volume on the worker. 161 backend tests, 28 frontend tests, typecheck/build.
  - Superadmin database backup/restore (2026-10-31): added `/admin/backups` plus sidebar and admin-home shortcuts. Superadmins can create, list, download, delete and restore portable SQL backups stored in a dedicated `backups` volume. Restores require an exact `RESTORE` confirmation, validate the SQL dump, create an automatic pre-restore safety backup and run through psql in one transaction; failures roll back and successes are audited. Added `postgresql-client` to the API image and stripped PostgreSQL 17-only dump directives for the project's PostgreSQL 16 database. 154 backend tests, 28 frontend tests, typecheck/build, and a live restore drill with data-count and `/ready` checks.
Active
- No unchecked phase-verification items remain; remaining `[~]` items are deliberate scope gaps below.
Blocked
- Playwright e2e suite not implemented (only Vitest exists).
- Whole-app frontend 60% coverage not achieved (only lib modules).
- Backend coverage 68.3% vs 80% target.
- Persian slug generation is ASCII + random suffix (D5).
- HTTPS config only (no live domain verification); Mellipayamak KYC external.
Next Move
1. Add Playwright e2e for home → search → business → quote → accept flow (or explicitly keep deferred).
2. Raise backend coverage toward 80% (outbox/worker, push provider, auth service are the biggest gaps).
3. Optional: Persian slug transliteration, `/admin/advertisements` alias, full-app frontend coverage.
4. Commit the uncommitted changes (all work currently on main working tree).
Relevant Files
- /Users/hamed/Projects/nomax/phase-verifications.md: checklist (all items now [x] or annotated [~]).
- /Users/hamed/Projects/nomax/proposal.md: original v1 spec.
- /Users/hamed/Projects/nomax/session.md: overrides/decisions that supersede proposal.
- /Users/hamed/Projects/nomax/docs/roadmap-status.md: phase hand-off status (Phases 0–10).
- /Users/hamed/Projects/nomax/backend/tests/test_endpoints_coverage.py: new §4 endpoint smoke coverage.
- /Users/hamed/Projects/nomax/backend/app/api/v1/businesses.py: business CRUD/license/tags/QR/analytics + me_router/uploads_router.
- /Users/hamed/Projects/nomax/backend/app/api/v1/utility.py: suggestions + approval now creates category/subcategory.
- /Users/hamed/Projects/nomax/backend/app/api/v1/admin.py: admin approval/reviews/stats/audit.
- /Users/hamed/Projects/nomax/frontend/src/features/me/: new /me layout + subroutes.
- /Users/hamed/Projects/nomax/frontend/src/lib/query.ts: `useApi` TanStack wrapper.
- /Users/hamed/Projects/nomax/frontend/src/app/App.tsx: routes (/me, /owner redirect).
- /Users/hamed/Projects/nomax/frontend/src/features/business/SearchPage.tsx: useInfiniteQuery search.
- /Users/hamed/Projects/nomax/docker-compose.prod.yml: production stack.
- /Users/hamed/Projects/nomax/deploy/: Caddyfile, backup script/timer, observability compose.
- /Users/hamed/Projects/nomax/frontend/vitest.config.ts: frontend test/coverage config.
Important Context
- Changes are uncommitted on main.
- Backend deps here are installed globally (Python 3.11); pytest-cov and segno were installed during this session. Run tests with `python3 -m pytest -q --cov=app --cov-fail-under=60`.
- Postgres runs on localhost:5433, Redis on 6380; API was smoke-tested on port 8010 because port 8001 is occupied by an unrelated docker-proxy.
- Migration 0004_reviews.py had stray EOF/echo done lines removed — migrations now load cleanly.
- Prod compose config check: `set -a && . ./.env.prod.example && set +a && docker compose -f docker-compose.prod.yml config`.
- Frontend test command: `npm run test` (Vitest + coverage thresholds); backend tests use SQLite + FakeRedis.
