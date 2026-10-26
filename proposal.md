# پروپوزال فنی توسعه پلتفرم نومکس
**مستند اجرایی برای AI Agent توسعه‌دهنده**

> **زمانه:** این سند برای راهنمایی AI Agent در پیاده‌سازی پروژه طراحی شده است. بخش‌های بدیهی (نصب پکیج، ساختار استاندارد FastAPI/React، اصول ORM، نکات عمومی امنیتی) حذف شده‌اند. تمرکز روی **الزامات کسب‌وکاری، تصمیمات طراحی غیراستاندارد، و منطق پیچیده‌ای** که Agent باید دقیقاً رعایت کند.

---

## ۱. مشخصات پروژه

| مورد | مقدار |
|---|---|
| **نام** | نومکس (NOMAX) |
| **نوع** | پلتفرم محلی معرفی کسب‌وکار و خدمات (B2B2C) |
| **مخاطب جغرافیایی** | شهر بهبهان، خوزستان |
| **منبع دیزاین** | https://ehsan-movahed.github.io/nomax/ |
| **Stack** | FastAPI + React 18 + PostgreSQL/PostGIS + Redis + MinIO |
| **بازه** | ۱۶ هفته (۴ ماه) |
| **نسخه هدف** | v1.0 (MVP) |

---

## ۲. الزامات کسب‌وکاری غیرقابل مذاکره

این قواعد از دیزاین فعلی استخراج شده‌اند و **دقیقاً باید پیاده‌سازی شوند**:

### ۲.۱ استعلام قیمت ناشناس (Anonymized Quote)
- شماره موبایل مشتری **تا لحظه پذیرش پیشنهاد** برای هیچ کسب‌وکاری قابل مشاهده نیست.
- پس از `POST /quotes/offers/{id}/accept`، شماره فقط برای `business_id` پذیرفته‌شده افشا می‌شود.
- هر کاربر **فقط یک درخواست فعال** همزمان می‌تواند داشته باشد (constraint در دیتابیس).

### ۲.۲ ساعات ارسال استعلام
- درخواست‌های **عادی**: فقط بین ۶:۰۰ تا ۲۱:۰۰ به کسب‌وکارهای مرتبط ارسال می‌شود.
- درخواست‌های **فوری (`is_urgent=true`)**: 
  - ۶:۰۰ تا ۲۱:۰۰ → به همه کسب‌وکارهای مرتبط
  - ۲۱:۰۰ تا ۶:۰۰ → فقط به کسب‌وکارهای دارای `is_24h=true`
- مهلت پاسخگویی به درخواست فوری: **۲ ساعت**.

### ۲.۳ جریان تأیید کسب‌وکار
```
pending → approved (با نشان اعتماد اگر پروانه تأیید شده) 
       → rejected (با reason)
```
- کسب‌وکار در حالت `pending` در نتایج جستجو **ظاهر نمی‌شود**.
- `is_verified` (نشان اعتماد) فقط با تأیید ادمین و داشتن پروانه کسب معتبر فعال می‌شود.
- `is_24h` (اورژانسی) توسط کاربر هنگام ثبت علامت می‌خورد اما توسط ادمین قابل حذف در صورت گزارش سوءاستفاده.

### ۲.۴ قوانین محدودیت ثبت
- هر `national_id` فقط می‌تواند **یک کسب‌وکار** ثبت کند (unique constraint).
- کد ملی و شماره موبایل از پروفایل احراز‌شده کاربر گرفته می‌شوند و **غیرقابل ویرایش** در فرم ثبت کسب‌وکار هستند.
- نظرات پس از تأیید ادمین نمایش داده می‌شوند (`status=pending` → `approved`/`rejected`).
- هر کسب‌وکار حداکثر **۳ برچسب سفارشی** می‌تواند اضافه کند.

### ۲.۵ دسته‌بندی بومی‌شده
- **۱۸ دسته اصلی** و **۱۵۰+ زیردسته** با آیکون و نام فارسی (داده seed در `categories.json`).
- کاربر می‌تواند «پیشنهاد دسته جدید» بدهد که به ادمین می‌رود.
- تا تأیید ادمین، کسب‌وکار با دسته پیشنهادی در دسته «سایر» قرار می‌گیرد.

---

## ۳. مدل داده (Entity Schema)

> Agent باید این موجودیت‌ها را به‌صورت SQLAlchemy models پیاده‌سازی کند. فیلدهای `created_at`, `updated_at`, `deleted_at` (soft delete) روی همه جداول الزامی است.

### ۳.۱ جداول اصلی

```python
# User
class User:
    id: UUID [PK]
    phone: str(11)            # unique, validated: 09xxxxxxxxx
    national_id: str(10)      # unique, validated: Iranian checksum
    full_name: str
    role: enum['customer', 'owner', 'admin']
    is_phone_verified: bool
    last_login_at: datetime

# Business
class Business:
    id: UUID [PK]
    owner_id: UUID [FK → User]
    category_id: int [FK]
    subcategory_id: int [FK, nullable]
    name: str
    slug: str                 # unique, generated from name
    short_description: str(120)
    description: text
    phone_business: str(11)   # optional, separate from owner phone
    address: str              # street detail only, city is fixed: "بهبهان"
    geo: Point                # PostGIS, nullable
    instagram: str            # optional
    is_24h: bool              # emergency availability
    is_verified: bool         # trust badge (admin approved + license)
    status: enum['pending', 'approved', 'rejected']
    rejection_reason: str     # nullable
    rating_avg: float         # cached, updated on review insert
    rating_count: int         # cached
    profile_image_url: str    # MinIO object key
    license_id: UUID [FK → License, nullable]

# License (پروانه کسب)
class License:
    id: UUID [PK]
    business_id: UUID [FK]
    license_number: str       # شماره صنفی
    image_url: str            # MinIO object key, max 150KB after compression
    is_verified_by_admin: bool

# Category / Subcategory
class Category:
    id: int [PK]
    name: str
    slug: str                 # unique
    icon: str                 # emoji or icon name
    sort_order: int
    is_active: bool

class Subcategory:
    id: int [PK]
    category_id: int [FK]
    name: str
    slug: str
    icon: str
    sort_order: int

# Tag (many-to-many with Business)
class Tag:
    id: int [PK]
    name: str
    is_custom: bool           # true = user-added, false = standard
    status: enum['pending', 'approved', 'rejected']

class BusinessTag:            # association table
    business_id: UUID [FK]
    tag_id: int [FK]

# Review
class Review:
    id: UUID [PK]
    business_id: UUID [FK]
    user_id: UUID [FK]
    rating: int(1..5)
    comment: str(300)         # nullable
    author_name: str          # optional, displayed name
    reply: str(250)           # owner's reply, nullable
    replied_at: datetime
    status: enum['pending', 'approved', 'rejected']

# QuoteRequest
class QuoteRequest:
    id: UUID [PK]
    user_id: UUID [FK]
    category_id: int [FK]
    subcategory_id: int [FK, nullable]
    item_description: text
    address: str              # required, text
    neighborhood: str         # optional
    geo: Point                # optional but recommended
    is_urgent: bool
    status: enum['active', 'accepted', 'expired', 'cancelled']
    expires_at: datetime      # = created_at + 2h if urgent, else +24h
    accepted_offer_id: UUID [FK → QuoteOffer, nullable]
    phone_revealed_to: UUID [FK → Business, nullable]  # set on accept

# QuoteOffer
class QuoteOffer:
    id: UUID [PK]
    request_id: UUID [FK]
    business_id: UUID [FK]
    price: decimal(12, 0)     # IRR
    brand: str                # optional
    notes: text               # optional
    status: enum['pending', 'accepted', 'rejected', 'expired']
```

### ۳.۲ جداول تکمیلی

```python
class Notification:           # web push queue
    id: UUID [PK]
    user_id: UUID [FK]
    type: enum['new_quote_request', 'new_offer', 'offer_accepted', 'review_reply']
    payload: JSONB
    is_read: bool
    created_at: datetime

class DeviceSubscription:     # VAPID web push
    id: UUID [PK]
    user_id: UUID [FK]
    endpoint: str
    p256dh_key: str
    auth_key: str
    is_active: bool

class CategorySuggestion:
    id: UUID [PK]
    user_id: UUID [FK]
    type: enum['new_subcategory', 'new_category']
    parent_category_id: int [FK, nullable]
    suggested_name: str
    description: str
    status: enum['pending', 'approved', 'rejected']

class Advertisement:
    id: UUID [PK]
    title: str
    image_url: str
    target_url: str
    placement: enum['home_banner', 'category_sidebar', 'search_top']
    starts_at: datetime
    ends_at: datetime
    is_active: bool

class ContactMessage:
    id: UUID [PK]
    name: str
    phone: str
    subject: str
    body: text
    is_read: bool
```

### ۳.۳ ایندکس‌های حیاتی

```sql
CREATE INDEX idx_businesses_geo ON businesses USING GIST (geo);
CREATE INDEX idx_businesses_status ON businesses (status) WHERE status = 'approved';
CREATE INDEX idx_businesses_category ON businesses (category_id, subcategory_id);
CREATE INDEX idx_quotes_active ON quote_requests (user_id) WHERE status = 'active';
CREATE INDEX idx_offers_pending ON quote_offers (request_id) WHERE status = 'pending';
CREATE INDEX idx_reviews_business ON reviews (business_id, status);
```

---

## ۴. API Endpoints

> پیشوند: `/api/v1` · احراز هویت: JWT Bearer (به‌جز endpoints عمومی) · پاسخ: `{ data, meta, error }`

### ۴.۱ Auth (OTP-based, no password)

| Method | Path | Body | Role | Note |
|---|---|---|---|---|
| POST | `/auth/otp/request` | `{ phone }` | public | rate limit: 3/hour/IP, TTL 2 min |
| POST | `/auth/otp/verify` | `{ phone, code }` | public | returns `{ access, refresh }` |
| POST | `/auth/refresh` | `{ refresh }` | user | rotate refresh token |
| POST | `/auth/logout` | — | user | blacklist refresh in Redis |
| GET  | `/auth/me` | — | user | returns user profile |

### ۴.۲ Catalog (Public)

| Method | Path | Query | Note |
|---|---|---|---|
| GET | `/categories` | — | 18 main categories with subcategory count |
| GET | `/categories/{id}/subcategories` | — | — |
| GET | `/businesses` | `lat, lng, radius_km, cat, subcat, q, sort, cursor` | sort: `nearest\|top\|newest\|urgent` |
| GET | `/businesses/{slug}` | — | includes reviews (approved only) |
| GET | `/businesses/{id}/qr` | — | returns PNG or SVG |

### ۴.3 Business Management

| Method | Path | Role | Note |
|---|---|---|---|
| POST | `/businesses` | customer → becomes owner | 3-step form, status=pending |
| PATCH | `/businesses/{id}` | owner (own only) | edits don't reset status unless critical fields changed |
| DELETE | `/businesses/{id}` | owner (own only) | soft delete |
| POST | `/businesses/{id}/reviews` | customer | one review per user per business |
| POST | `/reviews/{id}/reply` | owner (of reviewed business) | text ≤ 250 chars |

### ۴.۴ Quote Flow (Critical Path)

| Method | Path | Role | Note |
|---|---|---|---|
| POST | `/quotes/requests` | customer | one active request per user; sets `expires_at` |
| GET | `/quotes/requests/mine` | customer | includes offers count |
| POST | `/quotes/requests/{id}/cancel` | customer | sets status=cancelled |
| GET | `/quotes/requests/incoming` | owner | businesses matching category + geo radius (10km) |
| POST | `/quotes/offers` | owner | one offer per business per request |
| PATCH | `/quotes/offers/{id}/accept` | customer | sets `phone_revealed_to`, expires other offers |

### ۴.۵ Owner Panel

| Method | Path | Role |
|---|---|---|
| GET | `/me/businesses` | owner |
| GET | `/me/businesses/{id}/analytics` | owner (own) |
| GET | `/me/notifications` | owner |
| POST | `/notifications/subscribe` | user (VAPID payload) |

### ۴.۶ Admin

| Method | Path | Note |
|---|---|---|
| GET | `/admin/businesses?status=pending` | paginated |
| PATCH | `/admin/businesses/{id}/approve` | optional: `verify_license=true` |
| PATCH | `/admin/businesses/{id}/reject` | body: `{ reason }` |
| PATCH | `/admin/businesses/{id}/toggle-24h` | remove badge on abuse report |
| GET | `/admin/reviews?status=pending` | — |
| PATCH | `/admin/reviews/{id}/approve` | — |
| PATCH | `/admin/reviews/{id}/reject` | — |
| GET | `/admin/category-suggestions?status=pending` | — |
| POST | `/admin/categories` | create new category/subcategory from suggestion |
| POST | `/admin/advertisements` | CRUD |
| GET | `/admin/stats/overview` | counts: pending, approved, rejected, urgent, today |

### ۴.۷ Utility

| Method | Path | Note |
|---|---|---|
| POST | `/uploads/image` | multipart, max 5MB, auto-compress to ≤150KB, returns MinIO key |
| POST | `/suggestions/categories` | body: `{ type, parent_id?, name, description }` |
| GET | `/health` | liveness |
| GET | `/ready` | readiness (db + redis ping) |

---

## ۵. منطق پیچیده (Must Implement)

### ۵.۱ تخصیص استعلام به کسب‌وکارها (Quote Dispatch)

وقتی `POST /quotes/requests` صادر می‌شود، Celery task زیر اجرا می‌شود:

```python
@celery.task
def dispatch_quote_request(request_id: str):
    req = get_quote_request(request_id)
    now = timezone.now()
    
    # Determine target window
    is_daytime = 6 <= now.hour < 21
    
    # Find candidate businesses
    candidates = Business.objects.filter(
        category_id=req.category_id,
        status='approved',
    )
    if req.subcategory_id:
        candidates = candidates.filter(subcategory_id=req.subcategory_id)
    
    # Geo filter (10km radius) — skip if req.geo is None
    if req.geo:
        candidates = candidates.filter(
            geo__dwithin=(req.geo, 10000)  # meters
        )
    
    # Time-of-day filter
    if not is_daytime:
        candidates = candidates.filter(is_24h=True)
    
    # Send web push to each candidate
    for biz in candidates:
        send_push_notification.delay(biz.owner_id, {
            'type': 'new_quote_request',
            'request_id': str(req.id),
            'item': req.item_description[:80],
            'is_urgent': req.is_urgent,
        })
    
    # Schedule expiration
    expires_at = req.expires_at
    expire_quote_request.apply_async(args=[request_id], eta=expires_at)
```

### ۵.۲ محاسبه میانگین امتیاز (Rating Aggregation)

برای جلوگیری از N+1 query، `rating_avg` و `rating_count` در جدول `Business` کش می‌شوند:

```python
# Trigger: after INSERT on Review with status='approved'
def recalculate_business_rating(business_id):
    stats = Review.objects.filter(
        business_id=business_id,
        status='approved'
    ).aggregate(
        avg=Avg('rating'),
        count=Count('id')
    )
    Business.objects.filter(id=business_id).update(
        rating_avg=round(stats['avg'] or 0, 2),
        rating_count=stats['count']
    )
```

### ۵.۳ Web Push (VAPID)

- کلیدهای VAPID در `.env` (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT=mailto:...`).
- کتابخانه Python: `pywebpush`.
- Frontend با `service worker` + `PushManager.subscribe` در `notifications/subscribe` ثبت می‌کند.
- payload JSON حداکثر ۴KB.

### ۵.۴ اعتبارسنجی کد ملی ایرانی

```python
def validate_iranian_national_id(nid: str) -> bool:
    if not re.match(r'^\d{10}$', nid):
        return False
    digits = [int(d) for d in nid]
    checksum = digits[-1]
    weights = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(d * w for d, w in zip(digits[:9], weights))
    remainder = total % 11
    expected = remainder if remainder < 2 else 11 - remainder
    return expected == checksum
```

این validator باید در Pydantic schema برای `User.national_id` استفاده شود.

### ۵.۵ تولید Slug

```python
def generate_business_slug(name: str, owner_id: str) -> str:
    # Use owner_id suffix to avoid collision
    base = slugify_persian(name)  # preserves Persian chars, replaces space with -
    return f"{base}-{owner_id.hex[:8]}"
```

برای `slugify_persian` از کتابخانه `python-slugify` با `allow_unicode=True` استفاده شود.

### ۵.۶ فشرده‌سازی تصویر

```python
from PIL import Image
import io

def compress_image(image_bytes: bytes, max_size_kb: int = 150) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    # Resize if too large
    if max(img.size) > 1200:
        img.thumbnail((1200, 1200))
    # Iterative quality reduction
    for quality in [85, 75, 65, 55]:
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=quality, optimize=True)
        if buf.tell() <= max_size_kb * 1024:
            return buf.getvalue()
    return buf.getvalue()
```

---

## ۶. Frontend — مسیرها و State

### ۶.۱ Routes

```
/                           # home (search + categories + recent)
/search?q=&cat=&sort=       # search results
/businesses/{slug}          # business detail
/categories                 # all 18 categories tree
/quote/new                  # quote request form
/quote/mine                 # user's quote requests
/business/new               # 3-step registration
/me                         # owner panel
  /me/businesses
  /me/businesses/{id}/edit
  /me/notifications
  /me/analytics
/admin
  /admin/businesses
  /admin/reviews
  /admin/suggestions
  /admin/advertisements
/about
/contact
/rules
```

### ۶.۲ State Management

- **Server state:** TanStack Query با staleTime 60s برای categories، 30s برای businesses.
- **Client state:** Zustand stores:
  - `useAuthStore`: user, tokens, login/logout
  - `useUiStore`: sidebar open, theme, current location (geo)
  - `useQuoteStore`: draft of current quote request (localStorage persistence)

### ۶.۳ نقشه (Leaflet)

- Tile provider: OpenStreetMap (رایگان، بدون API key).
- مرکز پیش‌فرض: بهبهان `30.6380, 50.8380`، zoom 13.
- مارکر کسب‌وکار با popup شامل نام، آدرس و دکمه «مسیریابی».
- انتخاب موقعیت هنگام ثبت کسب‌وکار با draggable marker.

---

## ۷. ساختار پروژه (Recommended)

```
nomax/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py          # pydantic-settings
│   │   │   ├── security.py        # JWT, OTP
│   │   │   ├── deps.py            # Depends: get_db, get_current_user
│   │   │   └── exceptions.py
│   │   ├── models/                # SQLAlchemy models (one file per entity)
│   │   ├── schemas/               # Pydantic v2 schemas
│   │   ├── api/v1/
│   │   │   ├── auth.py
│   │   │   ├── businesses.py
│   │   │   ├── categories.py
│   │   │   ├── quotes.py
│   │   │   ├── reviews.py
│   │   │   ├── admin.py
│   │   │   ├── uploads.py
│   │   │   └── notifications.py
│   │   ├── services/              # business logic (reusable)
│   │   │   ├── quote_dispatcher.py
│   │   │   ├── rating_aggregator.py
│   │   │   ├── push_sender.py
│   │   │   └── image_processor.py
│   │   ├── tasks/                 # Celery tasks
│   │   └── db/
│   │       ├── session.py
│   │       └── seed.py            # seed 18 categories
│   ├── alembic/                   # migrations
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── routes/
│   │   ├── components/
│   │   │   ├── ui/                # shadcn/ui
│   │   │   ├── BusinessCard.tsx
│   │   │   ├── QuoteForm.tsx
│   │   │   └── MapPicker.tsx
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── business/
│   │   │   ├── quote/
│   │   │   └── admin/
│   │   ├── api/                   # generated axios client + react-query hooks
│   │   ├── stores/                # zustand
│   │   └── lib/
│   ├── public/
│   │   └── sw.js                  # service worker for push
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml             # dev: api + web + db + redis + minio + celery
├── docker-compose.prod.yml
├── .github/workflows/ci.yml
└── README.md
```

---

## ۸. Environment Variables

```bash
# Backend
DATABASE_URL=postgresql+asyncpg://nomax:secret@db:5432/nomax
REDIS_URL=redis://redis:6379/0
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET=nomax

JWT_SECRET=...                    # 32+ random bytes
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=30

OTP_TTL_SECONDS=120
OTP_RATE_LIMIT_PER_HOUR=3

VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_SUBJECT=mailto:admin@nomax.local

SMS_PROVIDER=kavenegar            # or farazsms
SMS_API_KEY=...
SMS_SENDER_NUMBER=...

# Celery
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_VAPID_PUBLIC_KEY=...
VITE_MAP_CENTER_LAT=30.6380
VITE_MAP_CENTER_LNG=50.8380
VITE_MAP_DEFAULT_ZOOM=13
```

---

## ۹. Seed Data — ۱۸ دسته اصلی

این داده‌ها در `app/db/seed.py` باید به‌صورت idempotent اجرا شوند. آیکون‌ها emoji هستند:

| slug | name | icon |
|---|---|---|
| automotive | خودرو و حمل‌ونقل | 🚗 |
| building | ساختمان و تأسیسات | 🏠 |
| digital | دیجیتال و فناوری | 📱 |
| food | خوراک و رستوران | 🍔 |
| agriculture | کشاورزی و دام | 🌾 |
| beauty | زیبایی و آرایش | 💗 |
| retail | خرده‌فروشی و پوشاک | 🛍 |
| repairs | خدمات عمومی و تعمیرات | 🔧 |
| education | آموزش و پرورش | 🎓 |
| medical | پزشکی و درمان | 🏥 |
| sports | ورزش و تفریح | 🏋 |
| arts | هنر و سرگرمی | 🎨 |
| pets | حیوانات خانگی | 🐾 |
| books | کتاب و نوشت‌افزار | 📚 |
| office-services | خدمات اداری و مالی | 💼 |
| accommodation | اقامت و گردشگری | 🏨 |
| tools | ابزار و تجهیزات | 🧰 |
| other | سایر | ❓ |

> زیردسته‌های هرکدام از فایل `categories.json` در ریپوی دیزاین استخراج شده و در seed قرار گیرد.

---

## ۱۰. تست — الزامات حداقلی

### ۱۰.۱ Backend (pytest)

```python
# tests/test_quotes.py
- test_customer_can_create_quote_request
- test_customer_cannot_have_two_active_requests
- test_urgent_request_only_dispatched_to_24h_businesses_at_night
- test_phone_revealed_only_after_offer_acceptance
- test_offer_cannot_be_submitted_for_expired_request
- test_business_owner_can_reply_to_review
- test_admin_can_approve_business
- test_rating_avg_updates_on_review_approval
- test_otp_rate_limit_enforced
```

### ۱۰.۲ Frontend (Vitest + Playwright)

```typescript
// e2e/quote-flow.spec.ts
- customer registers → creates business → admin approves → appears in search
- customer creates quote → owner sees it in panel → submits offer → customer accepts → phone revealed
- 24h business receives night quote, non-24h does not
```

### ۱۰.۳ پوشش حداقلی

- Backend: ۸۰٪ (خدمات quote, auth, admin حیاتی)
- Frontend: ۶۰٪ (کامپوننت‌های form و quote flow)

---

## ۱۱. دیپلوی

### ۱۱.۱ Production Topology

- سرور: VPS 8-core / 16GB RAM / 200GB SSD
- OS: Ubuntu 22.04 LTS
- Reverse proxy: Nginx 1.27 + Certbot (Let's Encrypt)
- Container runtime: Docker 24 + Compose v2
- Process manager: Docker Compose (یا systemd در صورت عدم استفاده از Swarm)

### ۱۱.۲ Backup

```bash
# cron job (daily at 03:00)
0 3 * * * pg_dump nomax | gzip > /backups/nomax_$(date +\%Y\%m\%d).sql.gz
0 3 * * * find /backups -name "nomax_*.sql.gz" -mtime +30 -delete
```

### ۱۱.۳ Health Checks

- `/health` → 200 OK (FastAPI process alive)
- `/ready` → 200 (DB + Redis reachable)
- Docker Compose `healthcheck` روی هر سرویس
- Uptime monitor: UptimeRobot یا Better Stack

---

## ۱۲. نقشه راه پس از v1.0 (Out of Scope برای این پروپوزال)

این موارد در معماری فعلی forward-compatible هستند اما در v1.0 پیاده نمی‌شوند:

- **v2.0** — درگاه پرداخت (زرین‌پال/آیدی‌پی) + کیف پول داخلی + کارمزد تراکنش
- **v2.5** — اپ موبایل React Native با همان API + push بومی FCM/APNs
- **v3.0** — داشبورد BI برای مالکان + سیستم توصیه‌گر ML + چت درون‌برنامه‌ای
- **v3.5** — استعلام خودکار از سامانه اصناف ایران + گسترش multi-tenant به شهرهای دیگر

---

## ۱۳. KPIهای موفقیت v1.0 (پس از ۶ ماه عرضه)

| شاخص | هدف |
|---|---|
| کسب‌وکار فعال و تأییدشده | ۵۰۰+ |
| کاربر ثبت‌نام‌شده با حداقل ۱ جستجو | ۱۰٬۰۰۰+ |
| استعلام موفق ماهانه | ۲٬۰۰۰+ |
| نرخ تبدیل استعلام به پیشنهاد پذیرفته‌شده | ۳۰٪ |
| میانگین امتیاز کسب‌وکارها | ≥ ۴.۰ از ۵ |
| زمان پاسخ میانگین به استعلام | < ۲ ساعت |
| نرخ بازگشت کاربر هفتگی | > ۳۵٪ |

---

## ۱۴. چک‌لیست تحویل (Definition of Done)

- [ ] تمام endpoints بخش ۴ پیاده‌سازی شده و تست شده‌اند
- [ ] منطق بخش ۵ (quote dispatch, rating, push, validation) کار می‌کند
- [ ] ۱۸ دسته + زیردسته‌ها seed شده‌اند
- [ ] احراز هویت OTP پیامکی فعال است (حتی با provider تست)
- [ ] web push در Chrome و Firefox کار می‌کند
- [ ] اپ روی `https://nomax.local` (یا دامنه واقعی) با SSL اجرا می‌شود
- [ ] backup روزانه PG فعال و تست‌شده است
- [ ] Sentry خطاهای production را لاگ می‌کند
- [ ] داکیومنت `/docs` (OpenAPI) قابل دسترسی است
- [ ] README پروژه شامل راه‌اندازی local dev است
