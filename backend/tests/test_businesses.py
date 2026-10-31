from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory

BEHBAHAN = {"lat": 30.6380, "lng": 50.8380}


@pytest_asyncio.fixture
async def catalog(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    categories = {
        item.slug: item for item in (await db_session.execute(select(Category))).scalars().all()
    }
    subcategories = {
        (item.category_id, item.slug): item
        for item in (await db_session.execute(select(Subcategory))).scalars().all()
    }
    return {"categories": categories, "subcategories": subcategories}


async def make_business(
    session,
    owner_id,
    category,
    subcategory=None,
    *,
    slug: str,
    name: str,
    lat: float = BEHBAHAN["lat"],
    lng: float = BEHBAHAN["lng"],
    status: BusinessStatus = BusinessStatus.APPROVED,
    rating: float = 0,
    rating_count: int = 0,
    is_24h: bool = False,
    created_at: datetime | None = None,
) -> Business:
    business = Business(
        owner_id=owner_id,
        category_id=category.id,
        subcategory_id=subcategory.id if subcategory else None,
        name=name,
        slug=slug,
        short_description=f"خدمات {name}",
        description=f"توضیحات کامل {name}",
        address="بهبهان، خیابان امام خمینی",
        phone_business="09120000000",
        geo_lat=lat,
        geo_lng=lng,
        status=status,
        rating_avg=rating,
        rating_count=rating_count,
        is_24h=is_24h,
        is_verified=True,
    )
    if created_at is not None:
        business.created_at = created_at
    session.add(business)
    await session.flush()
    return business


def _items(response):
    return response.json()["data"]["items"]


@pytest.mark.asyncio
async def test_only_approved_businesses_are_searchable(client, db_session, create_user, catalog):
    owner = await create_user("9130000001", full_name="حسین رضایی")
    automotive = catalog["categories"]["automotive"]
    mechanic = catalog["subcategories"][(automotive.id, "mechanic")]

    approved = await make_business(
        db_session, owner.id, automotive, mechanic, slug="approved-shop", name="مکانیکی تأییدشده"
    )
    await make_business(
        db_session,
        owner.id,
        automotive,
        mechanic,
        slug="pending-shop",
        name="مکانیکی در انتظار",
        status=BusinessStatus.PENDING,
    )
    await make_business(
        db_session,
        owner.id,
        automotive,
        mechanic,
        slug="rejected-shop",
        name="مکانیکی ردشده",
        status=BusinessStatus.REJECTED,
    )
    await db_session.commit()

    response = await client.get("/api/v1/businesses", params=BEHBAHAN)
    assert response.status_code == 200
    items = _items(response)
    assert [item["slug"] for item in items] == ["approved-shop"]
    assert items[0]["distance_m"] <= 10
    assert items[0]["category"]["slug"] == "automotive"
    assert items[0]["subcategory"]["slug"] == "mechanic"

    detail = await client.get(f"/api/v1/businesses/{approved.slug}")
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["name"] == "مکانیکی تأییدشده"
    assert body["reviews"] == []
    assert body["geo"] == {"lat": BEHBAHAN["lat"], "lng": BEHBAHAN["lng"]}
    assert body["owner"] == {"name": "حسین رضایی", "phone": "9130000001"}

    pending = await client.get("/api/v1/businesses/pending-shop")
    assert pending.status_code == 404
    assert pending.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_category_and_text_filters(client, db_session, create_user, catalog):
    owner = await create_user("9130000002")
    automotive = catalog["categories"]["automotive"]
    mechanic = catalog["subcategories"][(automotive.id, "mechanic")]
    food = catalog["categories"]["food"]
    restaurant = catalog["subcategories"][(food.id, "restaurant")]

    await make_business(db_session, owner.id, automotive, mechanic, slug="car-shop", name="مکانیکی امید")
    await make_business(db_session, owner.id, food, restaurant, slug="pizza-shop", name="پیتزا آتش")
    await db_session.commit()

    response = await client.get("/api/v1/businesses", params={"cat": "automotive"})
    assert [item["slug"] for item in _items(response)] == ["car-shop"]

    response = await client.get("/api/v1/businesses", params={"subcat": "restaurant"})
    assert [item["slug"] for item in _items(response)] == ["pizza-shop"]

    response = await client.get("/api/v1/businesses", params={"q": "پیتزا"})
    assert [item["slug"] for item in _items(response)] == ["pizza-shop"]

    response = await client.get("/api/v1/businesses", params={"q": "مکانیکی"})
    assert [item["slug"] for item in _items(response)] == ["car-shop"]

    response = await client.get("/api/v1/businesses", params={"cat": "not-a-category"})
    assert _items(response) == []


@pytest.mark.asyncio
async def test_radius_filter_and_sort_modes(client, db_session, create_user, catalog):
    owner = await create_user("9130000003")
    automotive = catalog["categories"]["automotive"]
    mechanic = catalog["subcategories"][(automotive.id, "mechanic")]
    now = datetime.now(timezone.utc)

    near = await make_business(
        db_session,
        owner.id,
        automotive,
        mechanic,
        slug="near-shop",
        name="نزدیک",
        lat=BEHBAHAN["lat"] + 0.009,
        lng=BEHBAHAN["lng"],
        rating=3.0,
        is_24h=True,
        created_at=now - timedelta(days=2),
    )
    mid = await make_business(
        db_session,
        owner.id,
        automotive,
        mechanic,
        slug="mid-shop",
        name="متوسط",
        lat=BEHBAHAN["lat"] + 0.045,
        lng=BEHBAHAN["lng"],
        rating=4.9,
        created_at=now - timedelta(days=1),
    )
    far = await make_business(
        db_session,
        owner.id,
        automotive,
        mechanic,
        slug="far-shop",
        name="دور",
        lat=BEHBAHAN["lat"] + 0.18,
        lng=BEHBAHAN["lng"],
        rating=4.8,
        created_at=now,
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/businesses", params={**BEHBAHAN, "radius_km": 10, "sort": "nearest"}
    )
    items = _items(response)
    assert [item["slug"] for item in items] == [near.slug, mid.slug]
    assert items[0]["distance_m"] < items[1]["distance_m"]

    response = await client.get(
        "/api/v1/businesses", params={**BEHBAHAN, "radius_km": 10, "sort": "top"}
    )
    assert [item["slug"] for item in _items(response)] == [mid.slug, near.slug]

    response = await client.get(
        "/api/v1/businesses", params={**BEHBAHAN, "radius_km": 10, "sort": "urgent"}
    )
    assert [item["slug"] for item in _items(response)] == [near.slug, mid.slug]

    response = await client.get("/api/v1/businesses", params={"sort": "newest"})
    assert [item["slug"] for item in _items(response)][0] == far.slug


@pytest.mark.asyncio
async def test_cursor_pagination(client, db_session, create_user, catalog):
    owner = await create_user("9130000004")
    automotive = catalog["categories"]["automotive"]
    mechanic = catalog["subcategories"][(automotive.id, "mechanic")]
    for index in range(5):
        await make_business(
            db_session,
            owner.id,
            automotive,
            mechanic,
            slug=f"shop-{index}",
            name=f"کسب‌وکار {index}",
            lat=BEHBAHAN["lat"] + index * 0.001,
        )
    await db_session.commit()

    first = await client.get("/api/v1/businesses", params={**BEHBAHAN, "limit": 2})
    assert first.status_code == 200
    assert len(_items(first)) == 2
    assert first.json()["meta"]["has_more"] is True
    cursor = first.json()["meta"]["next_cursor"]
    assert cursor

    second = await client.get(
        "/api/v1/businesses", params={**BEHBAHAN, "limit": 2, "cursor": cursor}
    )
    assert len(_items(second)) == 2
    second_cursor = second.json()["meta"]["next_cursor"]

    third = await client.get(
        "/api/v1/businesses", params={**BEHBAHAN, "limit": 2, "cursor": second_cursor}
    )
    assert len(_items(third)) == 1
    assert third.json()["meta"]["has_more"] is False
    assert third.json()["meta"]["next_cursor"] is None

    all_slugs = [
        item["slug"]
        for response in (first, second, third)
        for item in _items(response)
    ]
    assert len(all_slugs) == len(set(all_slugs)) == 5


@pytest.mark.asyncio
async def test_search_validation(client):
    response = await client.get("/api/v1/businesses", params={"lat": 30.6})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "lat_and_lng_required_together"

    response = await client.get("/api/v1/businesses", params={"lat": 30.6, "lng": 50.8, "cursor": "nope"})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "invalid_cursor"

    response = await client.get("/api/v1/businesses", params={"limit": 100})
    assert response.status_code == 422

    response = await client.get("/api/v1/businesses", params={"sort": "bogus"})
    assert response.status_code == 422
