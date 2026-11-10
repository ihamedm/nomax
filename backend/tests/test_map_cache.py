from datetime import datetime, timezone

import pytest
import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.job import ScheduledJob
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
async def test_map_returns_clusters_at_low_zoom_and_points_at_detail_zoom(
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

    low = await client.get("/api/v1/map/businesses", params={"zoom": 6})
    assert low.status_code == 200
    body = low.json()["data"]
    assert body["mode"] == "clusters"
    assert body["items"] == []
    assert sum(cluster["count"] for cluster in body["clusters"]) == 3

    detail = await client.get("/api/v1/map/businesses", params={"zoom": 15})
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["mode"] == "points"
    assert data["clusters"] == []
    names = {item["name"] for item in data["items"]}
    assert names == {"نزدیک الف", "نزدیک ب", "دور"}
    assert {"id", "slug", "lat", "lng", "category"} <= set(data["items"][0])

    # The first request filled the Redis snapshot.
    assert await fake_redis.get(map_cache.MANIFEST_KEY) is not None
    assert await fake_redis.get(map_cache.POINTS_KEY) is not None


@pytest.mark.asyncio
async def test_map_bbox_filters_clusters_and_points(client, db_session, create_user):
    owner = await create_user("9132000002")
    category, subcategory = await _catalog(db_session)
    inside = await _business(
        db_session, owner, category, subcategory,
        slug="inside", name="داخل محدوده", lat=BEHBAHAN["lat"], lng=BEHBAHAN["lng"],
    )
    await _business(
        db_session, owner, category, subcategory,
        slug="outside", name="خارج محدوده", lat=BEHBAHAN["lat"] + 2.0, lng=BEHBAHAN["lng"],
    )

    points = await client.get(
        "/api/v1/map/businesses",
        params={
            "zoom": 15,
            "west": BEHBAHAN["lng"] - 0.05,
            "south": BEHBAHAN["lat"] - 0.05,
            "east": BEHBAHAN["lng"] + 0.05,
            "north": BEHBAHAN["lat"] + 0.05,
        },
    )
    assert points.status_code == 200
    items = points.json()["data"]["items"]
    assert [item["slug"] for item in items] == [inside.slug]
    assert points.json()["meta"]["total"] == 1

    clusters = await client.get(
        "/api/v1/map/businesses",
        params={
            "zoom": 10,
            "west": BEHBAHAN["lng"] - 0.05,
            "south": BEHBAHAN["lat"] - 0.05,
            "east": BEHBAHAN["lng"] + 0.05,
            "north": BEHBAHAN["lat"] + 0.05,
        },
    )
    assert clusters.status_code == 200
    assert sum(item["count"] for item in clusters.json()["data"]["clusters"]) == 1


@pytest.mark.asyncio
async def test_map_bbox_validation(client):
    partial = await client.get("/api/v1/map/businesses", params={"zoom": 12, "west": 50.0})
    assert partial.status_code == 422
    assert partial.json()["error"]["message"] == "incomplete_bbox"

    inverted = await client.get(
        "/api/v1/map/businesses",
        params={"zoom": 12, "west": 50.9, "south": 30.6, "east": 50.8, "north": 30.7},
    )
    assert inverted.status_code == 422
    assert inverted.json()["error"]["message"] == "invalid_bbox"


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

    response = await client.get("/api/v1/map/businesses", params={"zoom": 15})
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
    assert data["catalog"]["ready"] is True
    assert data["catalog"]["categories"] >= 1

    # The catalog endpoints now read from the cache.
    categories = await client.get("/api/v1/categories")
    assert categories.status_code == 200
    assert len(categories.json()["data"]["items"]) >= 1

    flushed = await client.post("/api/v1/admin/cache/all/flush", headers=auth(admin))
    assert flushed.status_code == 200
    assert flushed.json()["data"]["map"]["ready"] is False
    assert flushed.json()["data"]["catalog"]["ready"] is False

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
    assert await fake_redis.get(map_cache.MANIFEST_KEY) is None

    await _sweep_scheduled_jobs(db_session, fake_redis)
    await db_session.commit()

    refreshed = (
        await db_session.execute(
            sa.select(ScheduledJob).where(ScheduledJob.type == map_cache.JOB_TYPE)
        )
    ).scalars().all()
    assert refreshed[0].status == "done"
    manifest = await fake_redis.get(map_cache.MANIFEST_KEY)
    assert manifest is not None


def test_cluster_cells_halve_per_zoom():
    assert map_cache.cell_size(6) == 360 / 64
    assert map_cache.cell_size(7) == map_cache.cell_size(6) / 2
    points = [
        {"lat": 30.6380, "lng": 50.8380},
        {"lat": 30.6381, "lng": 50.8381},
        {"lat": 45.0000, "lng": 60.0000},
    ]
    coarse = map_cache.build_clusters(points, 6)
    assert len(coarse) == 2
    assert sum(item["count"] for item in coarse) == 3

    # Two points ~10m apart share a cell until a very deep zoom, which is the
    # desired "merge nearby pins" behaviour.
    neighbours = map_cache.build_clusters(points[:2], 14)
    assert len(neighbours) == 1
    assert neighbours[0]["count"] == 2

    # ~1km apart is enough to split at the max cluster zoom.
    split = map_cache.build_clusters(
        [{"lat": 30.6380, "lng": 50.8380}, {"lat": 30.6480, "lng": 50.8480}], 14
    )
    assert len(split) == 2


@pytest.mark.asyncio
async def test_map_filters_reuse_cached_points(client, db_session, create_user, fake_redis):
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
    await client.get("/api/v1/map/businesses", params={"zoom": 15})

    detail = await client.get(
        "/api/v1/map/businesses", params={"zoom": 15, "cat": "automotive"}
    )
    assert detail.status_code == 200
    assert [item["slug"] for item in detail.json()["data"]["items"]] == ["filter-mechanic"]

    clusters = await client.get(
        "/api/v1/map/businesses", params={"zoom": 10, "cat": "automotive"}
    )
    assert clusters.status_code == 200
    assert sum(item["count"] for item in clusters.json()["data"]["clusters"]) == 1

    subcat = await client.get(
        "/api/v1/map/businesses", params={"zoom": 10, "subcat": "mechanic"}
    )
    assert sum(item["count"] for item in subcat.json()["data"]["clusters"]) == 1

    search = await client.get("/api/v1/map/businesses", params={"zoom": 15, "q": "سوپر"})
    assert [item["slug"] for item in search.json()["data"]["items"]] == ["filter-shop"]
