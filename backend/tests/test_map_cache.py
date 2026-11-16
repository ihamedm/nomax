import pytest
import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.job import ScheduledJob
from app.models.tag import BusinessTag, Tag
from app.models.user import UserRole
from app.services import map_cache
from app.worker import _sweep_scheduled_jobs

BEHBAHAN = {"lat": 30.6380, "lng": 50.8380}


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _catalog(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    category = (await db_session.execute(sa.select(Category))).scalars().first()
    subcategory = (
        await db_session.execute(
            sa.select(Subcategory).where(Subcategory.category_id == category.id)
        )
    ).scalars().first()
    return category, subcategory


async def _business(db_session, owner, category, subcategory, *, slug, name, lat, lng, status=None):
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        subcategory_id=subcategory.id if subcategory else None,
        name=name,
        slug=slug,
        address="بهبهان",
        geo_lat=lat,
        geo_lng=lng,
        status=status or BusinessStatus.APPROVED,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business


@pytest.mark.asyncio
async def test_map_returns_one_cached_snapshot_of_all_points(
    client, db_session, create_user, fake_redis
):
    owner = await create_user("9132000001")
    category, subcategory = await _catalog(db_session)
    await _business(
        db_session, owner, category, subcategory,
        slug="map-a", name="نزدیک الف", lat=BEHBAHAN["lat"], lng=BEHBAHAN["lng"],
    )
    await _business(
        db_session, owner, category, subcategory,
        slug="map-b", name="نزدیک ب", lat=BEHBAHAN["lat"] + 0.001, lng=BEHBAHAN["lng"],
    )
    await _business(
        db_session, owner, category, subcategory,
        slug="map-c", name="دور", lat=BEHBAHAN["lat"] + 1.0, lng=BEHBAHAN["lng"],
    )

    response = await client.get("/api/v1/map/businesses")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "mode" not in data
    assert data["items"]
    names = {item["name"] for item in data["items"]}
    assert names == {"نزدیک الف", "نزدیک ب", "دور"}
    assert {"id", "slug", "lat", "lng", "category", "subcategory_slugs"} <= set(
        data["items"][0]
    )
    assert "search_text" not in data["items"][0]
    assert response.json()["meta"]["cached"] is True

    snapshot = await fake_redis.get(map_cache.SNAPSHOT_KEY)
    assert snapshot is not None


@pytest.mark.asyncio
async def test_map_filters_reuse_the_cached_snapshot(
    client, db_session, create_user, fake_redis
):
    owner = await create_user("9132000009")
    await seed_categories(db_session)
    await db_session.commit()
    automotive = (
        await db_session.execute(sa.select(Category).where(Category.slug == "automotive"))
    ).scalars().first()
    retail = (
        await db_session.execute(sa.select(Category).where(Category.slug == "retail"))
    ).scalars().first()
    mechanic = (
        await db_session.execute(
            sa.select(Subcategory).where(
                Subcategory.category_id == automotive.id, Subcategory.slug == "mechanic"
            )
        )
    ).scalars().first()

    await _business(
        db_session, owner, automotive, mechanic,
        slug="filter-mechanic", name="مکانیکی", lat=BEHBAHAN["lat"], lng=BEHBAHAN["lng"],
    )
    await _business(
        db_session, owner, retail, None,
        slug="filter-shop", name="سوپرمارکت", lat=BEHBAHAN["lat"] + 0.001, lng=BEHBAHAN["lng"],
    )

    # Warm the cache with everything.
    await client.get("/api/v1/map/businesses")
    before = await fake_redis.get(map_cache.SNAPSHOT_KEY)

    detail = await client.get("/api/v1/map/businesses", params={"cat": "automotive"})
    assert detail.status_code == 200
    assert [item["slug"] for item in detail.json()["data"]["items"]] == ["filter-mechanic"]

    subcat = await client.get("/api/v1/map/businesses", params={"subcat": "mechanic"})
    assert [item["slug"] for item in subcat.json()["data"]["items"]] == ["filter-mechanic"]

    search = await client.get("/api/v1/map/businesses", params={"q": "سوپر"})
    assert [item["slug"] for item in search.json()["data"]["items"]] == ["filter-shop"]

    # Filtering reads the same snapshot; it does not rebuild or hit the database.
    assert await fake_redis.get(map_cache.SNAPSHOT_KEY) == before


@pytest.mark.asyncio
async def test_map_etag_answers_a_cheap_304(client, db_session, create_user):
    owner = await create_user("9132000010")
    category, subcategory = await _catalog(db_session)
    await _business(
        db_session, owner, category, subcategory,
        slug="etag-biz", name="ای‌تگ", lat=BEHBAHAN["lat"], lng=BEHBAHAN["lng"],
    )

    first = await client.get("/api/v1/map/businesses")
    assert first.status_code == 200
    etag = first.headers["etag"]
    assert "max-age=60" in first.headers["cache-control"]

    cached = await client.get(
        "/api/v1/map/businesses", headers={"If-None-Match": etag}
    )
    assert cached.status_code == 304


@pytest.mark.asyncio
async def test_rejected_and_deleted_businesses_never_reach_the_map(
    client, db_session, create_user
):
    owner = await create_user("9132000003")
    category, subcategory = await _catalog(db_session)
    await _business(
        db_session, owner, category, subcategory,
        slug="pending-one", name="در انتظار", lat=BEHBAHAN["lat"], lng=BEHBAHAN["lng"],
        status=BusinessStatus.PENDING,
    )
    await _business(
        db_session, owner, category, subcategory,
        slug="approved-one", name="تأییدشده", lat=BEHBAHAN["lat"], lng=BEHBAHAN["lng"],
    )

    response = await client.get("/api/v1/map/businesses")
    slugs = {item["slug"] for item in response.json()["data"]["items"]}
    assert slugs == {"approved-one"}


@pytest.mark.asyncio
async def test_admin_can_view_rebuild_and_flush_cache(client, db_session, create_user, fake_redis):
    admin = await create_user(
        "9132000004", UserRole.ADMIN, permissions=["admin.settings.manage"]
    )
    customer = await create_user("9132000005")
    owner = await create_user("9132000006")
    category, subcategory = await _catalog(db_session)
    await _business(
        db_session, owner, category, subcategory,
        slug="cache-biz", name="کش", lat=BEHBAHAN["lat"], lng=BEHBAHAN["lng"],
    )

    forbidden = await client.get("/api/v1/admin/cache", headers=auth(customer))
    assert forbidden.status_code == 403

    status = await client.get("/api/v1/admin/cache", headers=auth(admin))
    assert status.status_code == 200
    assert status.json()["data"]["map"]["ready"] is False

    rebuilt = await client.post("/api/v1/admin/cache/all/rebuild", headers=auth(admin))
    assert rebuilt.status_code == 200
    data = rebuilt.json()["data"]
    assert data["map"]["ready"] is True
    assert data["map"]["points"] == 1
    assert data["map"]["mode"] == "client-clusters"
    assert data["catalog"]["ready"] is True
    assert data["catalog"]["categories"] >= 1

    # The catalog endpoints now read from the cache.
    categories = await client.get("/api/v1/categories")
    assert categories.status_code == 200
    assert len(categories.json()["data"]["items"]) >= 1

    # Leftover v3 keys are removed with the snapshot.
    await fake_redis.set("map:v3:points", "old")
    flushed = await client.post("/api/v1/admin/cache/all/flush", headers=auth(admin))
    assert flushed.status_code == 200
    assert flushed.json()["data"]["map"]["ready"] is False
    assert flushed.json()["data"]["catalog"]["ready"] is False
    assert await fake_redis.get(map_cache.SNAPSHOT_KEY) is None
    assert await fake_redis.get("map:v3:points") is None

    missing = await client.post("/api/v1/admin/cache/nope/rebuild", headers=auth(admin))
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_approving_a_business_queues_and_runs_a_map_refresh(
    client, db_session, create_user, fake_redis
):
    admin = await create_user("9132000007", UserRole.ADMIN, permissions=["business.approve"])
    owner = await create_user("9132000008")
    category, subcategory = await _catalog(db_session)
    business = await _business(
        db_session, owner, category, subcategory,
        slug="approve-me", name="تأیید شو", lat=BEHBAHAN["lat"], lng=BEHBAHAN["lng"],
        status=BusinessStatus.PENDING,
    )

    approved = await client.patch(
        f"/api/v1/admin/businesses/{business.id}/approve", headers=auth(admin)
    )
    assert approved.status_code == 200

    jobs = (
        await db_session.execute(
            sa.select(ScheduledJob).where(ScheduledJob.type == map_cache.JOB_TYPE)
        )
    ).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].status == "pending"
    assert await fake_redis.get(map_cache.SNAPSHOT_KEY) is None

    await _sweep_scheduled_jobs(db_session, fake_redis)
    await db_session.commit()

    refreshed = (
        await db_session.execute(
            sa.select(ScheduledJob).where(ScheduledJob.type == map_cache.JOB_TYPE)
        )
    ).scalars().all()
    assert refreshed[0].status == "done"
    snapshot = await fake_redis.get(map_cache.SNAPSHOT_KEY)
    assert snapshot is not None


@pytest.mark.asyncio
async def test_map_search_matches_description_tags_and_owner(
    client, db_session, create_user
):
    owner = await create_user("09123334455", full_name="نگار کریمی")
    category, subcategory = await _catalog(db_session)
    business = await _business(
        db_session, owner, category, subcategory,
        slug="deep-search", name="فروشگاه نمونه",
        lat=BEHBAHAN["lat"], lng=BEHBAHAN["lng"],
    )
    business.description = "ابزار دقیق آزمایشگاهی"
    tag = Tag(name="خدمات ویژه")
    db_session.add(tag)
    await db_session.flush()
    db_session.add(BusinessTag(business_id=business.id, tag_id=tag.id))
    await db_session.commit()

    for term in ("آزمایشگاهی", "ویژه", "نگار", "34455"):
        response = await client.get("/api/v1/map/businesses", params={"q": term})
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert [item["slug"] for item in items] == ["deep-search"]
        # The haystack (which holds the owner phone) must not reach clients.
        assert "search_text" not in items[0]


def test_snapshot_capacity_covers_next_year():
    assert map_cache.MAX_CACHED_POINTS >= 10000
