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
- [ ] A6 Business lifecycle pending → approved/rejected(reason); pending hidden from search
- [x] A7 `is_verified` only via admin + valid license
- [x] A8 `is_24h` user-set, admin toggle on abuse
- [x] A9 One business per `national_id`
- [x] A10 National ID + phone read-only from verified profile
- [ ] A11 Reviews pending → approved/rejected
- [x] A12 Max 3 custom tags per business
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
- [x] B10 Notification (type + payload)
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
- [ ] GET /quotes/requests/mine
- [x] POST /quotes/requests/{id}/cancel
- [x] GET /quotes/requests/incoming
- [x] POST /quotes/offers (+ legacy path)
- [x] PATCH /quotes/offers/{id}/accept (+ legacy path)

### Owner panel (§4.5)
- [x] GET /me/businesses
- [x] GET /me/businesses/{id}/analytics
- [~] GET /me/notifications → `GET /notifications`
- [x] POST /notifications/subscribe replaced by `POST /devices`

### Admin (§4.6)
- [x] GET /admin/businesses?status=pending
- [x] PATCH /admin/businesses/{id}/approve|reject
- [x] PATCH /admin/businesses/{id}/toggle-24h
- [x] GET /admin/reviews?status=pending
- [x] review moderation via status PATCH + admin list
- [x] GET /admin/category-suggestions
- [x] POST /admin/categories (via suggestion approval)
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
- [x] D6 Image compression ≤150KB / 5MB limit

## E. Frontend (§6)

- [x] /
- [x] /search
- [x] /businesses/{slug}
- [x] /categories
- [x] /quote/new
- [x] /quote/mine
- [~] /business/new → `/businesses/new`
- [ ] /me + subroutes (only `/owner` stub)
- [x] admin businesses + reviews screens
- [~] /about, /contact, /rules (`/pages/:page` about+contact only)
- [ ] TanStack Query (hand-rolled fetch)
- [~] Zustand (auth + ui only; no quote store)
- [x] Neshan map (replaces OSM); verify draggable marker wired to form
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
- [ ] admin can approve business
- [x] rating_avg updates on review approval
- [x] OTP rate limit enforced (service + API tests)
- [~] Frontend Vitest ✅ (91.9% on lib); Playwright ❌
- [~] Backend coverage 71% (target 80%)
- [x] Frontend coverage 60%+ (Vitest, lib modules)

## I. Deploy (§11)

- [x] Nginx+Certbot → Caddy (equivalent)
- [x] Daily backup script + systemd timer
- [x] Restore drill executed (categories=18, businesses=1)
- [x] Compose healthchecks (api/worker-exempt/web/caddy/db/redis)
- [x] Uptime Kuma + GlitchTip compose

## J. Definition of Done (§14)

- [ ] All §4 endpoints implemented + tested
- [~] §5 logic (rating + NID only)
- [x] 18 categories seeded
- [x] OTP SMS active (console; Mellipayamak KYC external)
- [x] Web push removed per session decision
- [~] HTTPS config only
- [x] Daily backup active + tested
- [x] GlitchTip compose stack
- [x] /docs
- [x] README local setup
