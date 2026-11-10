"""Development-only demo businesses around Behbahan.

These are not production fixtures. The command refuses to run when
``APP_ENV=production`` and is idempotent by slug.
"""

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.user import User, UserRole

DEMO_OWNERS = [
    {"phone": "9130000001", "full_name": "مالک نمونه یک"},
    {"phone": "9130000002", "full_name": "مالک نمونه دو"},
    {"phone": "9130000003", "full_name": "مالک نمونه سه"},
    {"phone": "9130000004", "full_name": "مالک نمونه چهار"},
]

# lat/lng are around the Behbahan center used by the map and search defaults.
DEMO_BUSINESSES = [
    {
        "slug": "omid-mechanic",
        "name": "مکانیکی امید",
        "category": "automotive",
        "subcategory": "mechanic",
        "owner": 0,
        "short_description": "تعمیر تخصصی موتور و گیربکس خودرو",
        "description": "مجموعه مکانیکی امید با بیش از ۱۵ سال سابقه در زمینه تعمیر موتور، گیربکس، جلوبندی و دیاگ خودروهای ایرانی و خارجی فعالیت می‌کند.",
        "address": "بهبهان، بلوار شهید مطهری، جنب پمپ بنزین",
        "phone": "09133445501",
        "instagram": "omid.mechanic",
        "lat": 30.6385,
        "lng": 50.8390,
        "rating": 4.7,
        "rating_count": 38,
        "is_24h": True,
        "is_verified": True,
        "days_ago": 2,
    },
    {
        "slug": "behbahan-car-electric",
        "name": "برق خودرو بهبهان",
        "category": "automotive",
        "subcategory": "electric",
        "owner": 1,
        "short_description": "باتری، دینام، استارت و دیاگ برق خودرو",
        "description": "خدمات کامل برق خودرو شامل تعمیر دینام و استارت، فروش و نصب باتری، رفع ایراد سیم‌کشی و عیب‌یابی با دستگاه دیاگ.",
        "address": "بهبهان، خیابان طالقانی، نبش کوچه ۱۲",
        "phone": "09133445502",
        "instagram": "behbahan.car.electric",
        "lat": 30.6401,
        "lng": 50.8365,
        "rating": 4.5,
        "rating_count": 21,
        "is_24h": True,
        "is_verified": True,
        "days_ago": 6,
    },
    {
        "slug": "golestan-restaurant",
        "name": "رستوران سنتی گلستان",
        "category": "food",
        "subcategory": "restaurant",
        "owner": 2,
        "short_description": "غذاهای ایرانی اصیل با کیفیت خانگی",
        "description": "رستوران سنتی گلستان با فضای دنج و غذاهای ایرانی اصیل، میزبان خانواده‌های بهبهانی است. کباب، خورشت و دیزی سنتی در منوی روزانه.",
        "address": "بهبهان، میدان امام، ابتدای بازار قدیم",
        "phone": "09133445503",
        "instagram": "golestan.restaurant",
        "lat": 30.6362,
        "lng": 50.8412,
        "rating": 4.8,
        "rating_count": 124,
        "is_24h": False,
        "is_verified": True,
        "days_ago": 12,
    },
    {
        "slug": "atash-pizza",
        "name": "پیتزا آتش",
        "category": "food",
        "subcategory": "fastfood",
        "owner": 2,
        "short_description": "پیتزا و فست‌فود با پخت زغالی",
        "description": "پیتزا آتش با خمیر تازه و پخت زغالی، پیتزا، برگر و ساندویچ را تا نیمه‌شب به صورت بیرون‌بر و ارسال ارائه می‌دهد.",
        "address": "بهبهان، بلوار آزادی، روبه‌روی پارک شهر",
        "phone": "09133445504",
        "instagram": "atash.pizza",
        "lat": 30.6348,
        "lng": 50.8355,
        "rating": 4.3,
        "rating_count": 87,
        "is_24h": True,
        "is_verified": False,
        "days_ago": 1,
    },
    {
        "slug": "sabalan-cafe",
        "name": "کافه صبلان",
        "category": "food",
        "subcategory": "cafe",
        "owner": 3,
        "short_description": "قهوه تخصصی، کیک و فضای کار",
        "description": "کافه صبلان با قهوه تخصصی، کیک روز و فضای مناسب برای کار و مطالعه در قلب بهبهان.",
        "address": "بهبهان، خیابان شهید بهشتی، پلاک ۲۴",
        "phone": "09133445505",
        "instagram": "sabalan.cafe",
        "lat": 30.6395,
        "lng": 50.8420,
        "rating": 4.6,
        "rating_count": 55,
        "is_24h": False,
        "is_verified": False,
        "days_ago": 4,
    },
    {
        "slug": "labkhand-dental",
        "name": "کلینیک دندان‌پزشکی لبخند",
        "category": "medical",
        "subcategory": "dentist",
        "owner": 0,
        "short_description": "دندان‌پزشکی زیبایی و درمان",
        "description": "کلینیک دندان‌پزشکی لبخند با تجهیزات مدرن، خدمات درمانی و زیبایی دندان شامل ایمپلنت، لمینت و ترمیم را ارائه می‌دهد.",
        "address": "بهبهان، خیابان سعدی، ساختمان پزشکان لبخند",
        "phone": "09133445506",
        "instagram": "labkhand.dental",
        "lat": 30.6375,
        "lng": 50.8338,
        "rating": 4.9,
        "rating_count": 64,
        "is_24h": False,
        "is_verified": True,
        "days_ago": 20,
    },
    {
        "slug": "shafa-pharmacy",
        "name": "داروخانه شبانه‌روزی شفا",
        "category": "medical",
        "subcategory": "pharmacy",
        "owner": 1,
        "short_description": "داروخانه شبانه‌روزی و مشاوره دارویی",
        "description": "داروخانه شفا به صورت شبانه‌روزی خدمات دارویی، مکمل و مشاوره مصرف صحیح دارو ارائه می‌کند.",
        "address": "بهبهان، بلوار امام رضا، جنب بیمارستان",
        "phone": "09133445507",
        "instagram": "shafa.pharmacy",
        "lat": 30.6410,
        "lng": 50.8370,
        "rating": 4.4,
        "rating_count": 31,
        "is_24h": True,
        "is_verified": True,
        "days_ago": 30,
    },
    {
        "slug": "taban-appliance",
        "name": "تعمیرات لوازم خانگی تابان",
        "category": "repairs",
        "subcategory": "home_appliance",
        "owner": 2,
        "short_description": "تعمیر لباسشویی، یخچال و مایکروویو",
        "description": "خدمات تعمیر لوازم خانگی در محل، با گارانتی تعمیر و قطعات اصلی برای برندهای داخلی و خارجی.",
        "address": "بهبهان، خیابان فرهنگ، کوچه شهید احمدی",
        "phone": "09133445508",
        "instagram": "taban.repair",
        "lat": 30.6355,
        "lng": 50.8405,
        "rating": 4.2,
        "rating_count": 19,
        "is_24h": False,
        "is_verified": False,
        "days_ago": 8,
    },
    {
        "slug": "ziba-beauty",
        "name": "سالن زیبایی زیبا",
        "category": "beauty",
        "subcategory": "barber_women",
        "owner": 3,
        "short_description": "آرایش، رنگ و کراتین مو",
        "description": "سالن زیبایی زیبا با کادر مجرب، خدمات آرایش و پیرایش، رنگ و کراتین مو، میکاپ و ناخن را با رعایت کامل بهداشت ارائه می‌دهد.",
        "address": "بهبهان، خیابان ۱۵ خرداد، طبقه دوم",
        "phone": "09133445509",
        "instagram": "ziba.beauty",
        "lat": 30.6390,
        "lng": 50.8345,
        "rating": 4.7,
        "rating_count": 73,
        "is_24h": False,
        "is_verified": True,
        "days_ago": 15,
    },
    {
        "slug": "nakhl-hotel",
        "name": "هتل نخل بهبهان",
        "category": "accommodation",
        "subcategory": "hotel",
        "owner": 0,
        "short_description": "اقامت و پذیرایی در مرکز بهبهان",
        "description": "هتل نخل با اتاق‌های تمیز، صبحانه کامل و دسترسی آسان به مرکز شهر، پذیرای مسافران و مهمانان است.",
        "address": "بهبهان، بلوار شهید بهشتی، جنب پارک نخل",
        "phone": "09133445510",
        "instagram": "nakhl.hotel",
        "lat": 30.6420,
        "lng": 50.8320,
        "rating": 4.1,
        "rating_count": 28,
        "is_24h": True,
        "is_verified": False,
        "days_ago": 45,
    },
    {
        "slug": "nakhl-supermarket",
        "name": "سوپرمارکت نخل",
        "category": "retail",
        "subcategory": "supermarket",
        "owner": 1,
        "short_description": "خرید روزانه و ارسال رایگان",
        "description": "سوپرمارکت نخل با تنوع کامل مواد غذایی، شوینده و لوازم خانگی، خرید روزانه و ارسال رایگان در محدوده شهر.",
        "address": "بهبهان، خیابان امام خمینی، نبش کوچه ۸",
        "phone": "09133445511",
        "instagram": "nakhl.market",
        "lat": 30.6368,
        "lng": 50.8375,
        "rating": 4.0,
        "rating_count": 112,
        "is_24h": True,
        "is_verified": False,
        "days_ago": 3,
    },
    {
        "slug": "pars-plumbing",
        "name": "لوله‌کشی پارس",
        "category": "building",
        "subcategory": "plumbing",
        "owner": 2,
        "short_description": "لوله‌کشی آب، فاضلاب و رفع نشتی",
        "description": "خدمات لوله‌کشی ساختمان، تعمیر و رفع نشتی، نصب شیرآلات و پمپ آب با تیم مجرب و پاسخگویی سریع.",
        "address": "بهبهان، بلوار معلم، کوچه ۵",
        "phone": "09133445512",
        "instagram": "pars.plumbing",
        "lat": 30.6430,
        "lng": 50.8430,
        "rating": 4.5,
        "rating_count": 16,
        "is_24h": False,
        "is_verified": False,
        "days_ago": 9,
    },
    {
        "slug": "hamrah-mobile-repair",
        "name": "تعمیرات موبایل همراه",
        "category": "digital",
        "subcategory": "mobile_repair",
        "owner": 3,
        "short_description": "تعمیر تخصصی موبایل و تبلت",
        "description": "تعمیرات تخصصی موبایل و تبلت شامل تعویض ال‌سی‌دی، باتری، سوکت شارژ، برد و بازیابی اطلاعات با قطعات باکیفیت.",
        "address": "بهبهان، بازار مرکزی، پاساژ ارغوان",
        "phone": "09133445513",
        "instagram": "hamrah.mobile",
        "lat": 30.6388,
        "lng": 50.8308,
        "rating": 4.6,
        "rating_count": 41,
        "is_24h": False,
        "is_verified": True,
        "days_ago": 18,
    },
    {
        "slug": "aria-gym",
        "name": "باشگاه ورزشی آریا",
        "category": "sports",
        "subcategory": "gym",
        "owner": 0,
        "short_description": "بدنسازی، ایروبیک و مربی خصوصی",
        "description": "باشگاه آریا با تجهیزات کامل بدنسازی، کلاس‌های ایروبیک و مربی خصوصی، برنامه تمرینی و تغذیه ارائه می‌دهد.",
        "address": "بهبهان، بلوار دانشگاه، جنب استخر",
        "phone": "09133445514",
        "instagram": "aria.gym",
        "lat": 30.6335,
        "lng": 50.8450,
        "rating": 4.4,
        "rating_count": 37,
        "is_24h": False,
        "is_verified": False,
        "days_ago": 25,
    },
    {
        "slug": "mehr-language",
        "name": "آموزشگاه زبان مهر",
        "category": "education",
        "subcategory": "language",
        "owner": 1,
        "short_description": "آموزش زبان انگلیسی و آیلتس",
        "description": "آموزشگاه زبان مهر دوره‌های انگلیسی، آیلتس و مکالمه را با اساتید مجرب و کلاس‌های کوچک برگزار می‌کند.",
        "address": "بهبهان، خیابان دانش، ساختمان مهر",
        "phone": "09133445515",
        "instagram": "mehr.language",
        "lat": 30.6405,
        "lng": 50.8415,
        "rating": 4.8,
        "rating_count": 52,
        "is_24h": False,
        "is_verified": True,
        "days_ago": 33,
    },
    {
        "slug": "behbahan-taxi",
        "name": "آژانس تاکسی بهبهان",
        "category": "automotive",
        "subcategory": "taxi",
        "owner": 2,
        "short_description": "تاکسی شهری، دربست و سرویس مدارس",
        "description": "آژانس تاکسی بهبهان خدمات تاکسی شهری، دربست، فرودگاه و سرویس مدارس را به صورت شبانه‌روزی ارائه می‌دهد.",
        "address": "بهبهان، میدان آزادی، جنب بانک ملی",
        "phone": "09133445516",
        "instagram": "behbahan.taxi",
        "lat": 30.6392,
        "lng": 50.8368,
        "rating": 4.0,
        "rating_count": 44,
        "is_24h": True,
        "is_verified": False,
        "days_ago": 5,
    },
    {
        "slug": "nilgoon-carwash",
        "name": "کارواش نیلگون",
        "category": "repairs",
        "subcategory": "carwash",
        "owner": 3,
        "short_description": "کارواش بخار و تخصصی خودرو",
        "description": "کارواش نیلگون با شست‌وشوی بخار، صابون‌کشی و واکس بدنه، خدمات شست‌وشوی خودرو را در محل ارائه می‌کند.",
        "address": "بهبهان، بلوار ساحلی، نبش خیابان ۱۷",
        "phone": "09133445517",
        "instagram": "nilgoon.carwash",
        "lat": 30.6370,
        "lng": 50.8460,
        "rating": 4.3,
        "rating_count": 25,
        "is_24h": True,
        "is_verified": False,
        "days_ago": 11,
    },
    {
        "slug": "sandwich-waiting",
        "name": "ساندویچ در انتظار تأیید",
        "category": "food",
        "subcategory": "sandwich",
        "owner": 3,
        "short_description": "این کسب‌وکار هنوز تأیید نشده است",
        "description": "رکورد نمونه برای آزمون عدم نمایش کسب‌وکار در انتظار تأیید.",
        "address": "بهبهان، خیابان نمونه",
        "phone": "09133445518",
        "instagram": None,
        "lat": 30.6377,
        "lng": 50.8395,
        "rating": 0,
        "rating_count": 0,
        "is_24h": False,
        "is_verified": False,
        "status": BusinessStatus.PENDING,
        "days_ago": 0,
    },
    {
        "slug": "gift-rejected",
        "name": "فروشگاه هدیه ردشده",
        "category": "retail",
        "subcategory": "gifts",
        "owner": 2,
        "short_description": "این کسب‌وکار رد شده است",
        "description": "رکورد نمونه برای آزمون عدم نمایش کسب‌وکار ردشده.",
        "address": "بهبهان، خیابان نمونه",
        "phone": "09133445519",
        "instagram": None,
        "lat": 30.6371,
        "lng": 50.8330,
        "rating": 0,
        "rating_count": 0,
        "is_24h": False,
        "is_verified": False,
        "status": BusinessStatus.REJECTED,
        "rejection_reason": "مدارک ناقص",
        "days_ago": 0,
    },
]


async def seed_demo_businesses(session: AsyncSession, reset: bool = False) -> dict[str, int]:
    if settings.APP_ENV == "production":
        raise RuntimeError("demo businesses cannot be seeded in production")

    slugs = [item["slug"] for item in DEMO_BUSINESSES]
    if reset:
        await session.execute(sa.delete(Business).where(Business.slug.in_(slugs)))
        await session.flush()

    categories = {
        category.slug: category
        for category in (await session.execute(select(Category))).scalars().all()
    }
    subcategories = {
        (sub.category_id, sub.slug): sub
        for sub in (await session.execute(select(Subcategory))).scalars().all()
    }

    owners: list[User] = []
    for item in DEMO_OWNERS:
        owner = (
            await session.execute(select(User).where(User.phone == item["phone"]))
        ).scalar_one_or_none()
        if owner is None:
            owner = User(
                phone=item["phone"],
                full_name=item["full_name"],
                role=UserRole.OWNER,
                permissions=[],
                is_phone_verified=True,
            )
            session.add(owner)
            await session.flush()
        else:
            owner.full_name = owner.full_name or item["full_name"]
            owner.deleted_at = None
            owner.role = UserRole.OWNER
        owners.append(owner)

    created = 0
    updated = 0
    now = datetime.now(timezone.utc)

    for item in DEMO_BUSINESSES:
        category = categories.get(item["category"])
        if category is None:
            raise RuntimeError(f"category {item['category']} is not seeded")
        subcategory = subcategories.get((category.id, item["subcategory"]))
        if subcategory is None:
            raise RuntimeError(f"subcategory {item['subcategory']} is not seeded")

        business = (
            await session.execute(select(Business).where(Business.slug == item["slug"]))
        ).scalar_one_or_none()

        if business is None:
            business = Business(
                slug=item["slug"],
                owner_id=owners[item["owner"]].id,
                category_id=category.id,
                subcategory_id=subcategory.id,
                created_at=now - timedelta(days=item["days_ago"]),
            )
            session.add(business)
            created += 1
        else:
            updated += 1

        business.name = item["name"]
        business.short_description = item["short_description"]
        business.description = item["description"]
        business.address = item["address"]
        business.phone_business = item["phone"]
        business.instagram = item["instagram"]
        business.geo_lat = item["lat"]
        business.geo_lng = item["lng"]
        business.status = item.get("status", BusinessStatus.APPROVED)
        business.rejection_reason = item.get("rejection_reason")
        # Ratings are derived from approved public reviews only.
        business.rating_avg = 0
        business.rating_count = 0
        business.is_24h = item["is_24h"]
        business.is_verified = item["is_verified"]
        business.deleted_at = None

    await session.flush()
    return {"created": created, "updated": updated, "total": len(DEMO_BUSINESSES)}
