"""Versioned map snapshot consumed by the search page.

Approved businesses that have coordinates are materialised once into a single
Redis value:

* ``map:v4:snapshot`` – manifest, compact point list and the private search
  haystack used to filter the map.

The snapshot is rebuilt by a worker job after a business changes state and on
demand from the dashboard. A cold cache is filled synchronously on the first
map request, so the map never depends on the worker being up.

Clustering happens in the browser (Supercluster) from this snapshot. A single
atomic value is enough at the city scale (thousands of businesses): it removes
per-zoom/pre-computed grids, keeps cluster counts truthful, and makes panning
and zooming independent of the network.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.tag import BusinessTag, Tag
from app.models.user import User

logger = logging.getLogger("nomax.map_cache")

CACHE_VERSION = 4
SNAPSHOT_KEY = f"map:v{CACHE_VERSION}:snapshot"

# The snapshot is intentionally larger than the current city size; the next
# growth step (10k businesses) must not silently truncate the map.
MAX_CACHED_POINTS = 20000

# Keeps a stale snapshot from living forever if the worker never runs.
CACHE_TTL_SECONDS = 7 * 24 * 3600

JOB_TYPE = "map_cache.refresh"

# Older versions kept nine cluster keys and a 16 MB point list. Removing them
# on flush keeps Redis tidy after an upgrade.
_LEGACY_KEYS = [
    "map:v3:manifest",
    "map:v3:points",
    *[f"map:v3:clusters:{zoom}" for zoom in range(6, 15)],
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _category_ref(category: Category | None) -> dict | None:
    if category is None:
        return None
    return {
        "id": category.id,
        "slug": category.slug,
        "name": category.name,
        "icon": category.icon,
    }


async def _load_points(session: AsyncSession) -> tuple[list[dict], dict[str, str]]:
    rows = (
        await session.execute(
            sa.select(Business, Category, User)
            .join(Category, Business.category_id == Category.id)
            .join(User, Business.owner_id == User.id)
            .where(
                Business.status == BusinessStatus.APPROVED,
                Business.deleted_at.is_(None),
                Business.geo_lat.is_not(None),
                Business.geo_lng.is_not(None),
                Category.deleted_at.is_(None),
            )
            .order_by(Business.id)
            .limit(MAX_CACHED_POINTS)
        )
    ).all()

    business_ids = [business.id for business, _, _ in rows]
    tags_by_business: dict = {}
    if business_ids:
        tag_rows = (
            await session.execute(
                sa.select(BusinessTag.business_id, Tag.name)
                .join(Tag, Tag.id == BusinessTag.tag_id)
                .where(
                    BusinessTag.business_id.in_(business_ids),
                    Tag.deleted_at.is_(None),
                )
            )
        ).all()
        for business_id, tag_name in tag_rows:
            tags_by_business.setdefault(business_id, []).append(tag_name)

    points: list[dict] = []
    search: dict[str, str] = {}
    for business, category, owner in rows:
        subcategories = [
            _category_ref(subcategory)
            for subcategory in business.subcategories
            if subcategory.deleted_at is None
        ]
        primary = (
            _category_ref(business.subcategory)
            if business.subcategory is not None and business.subcategory.deleted_at is None
            else (subcategories[0] if subcategories else None)
        )
        if not subcategories and primary is not None:
            subcategories = [primary]

        subcategory_slugs = sorted(
            {
                item["slug"]
                for item in subcategories
                if item is not None
            }
            | ({primary["slug"]} if primary is not None else set())
        )
        points.append(
            {
                "id": str(business.id),
                "slug": business.slug,
                "name": business.name,
                "lat": round(float(business.geo_lat), 6),
                "lng": round(float(business.geo_lng), 6),
                "address": business.address,
                "rating_avg": round(business.rating_avg or 0, 2),
                "rating_count": business.rating_count or 0,
                "like_count": business.like_count or 0,
                "is_24h": business.is_24h,
                "is_verified": business.is_verified,
                "is_license_verified": business.is_license_verified,
                "profile_image_url": business.profile_image_url,
                "avatar_url": business.avatar_url,
                "category": _category_ref(category),
                "subcategory": primary,
                "subcategory_slugs": subcategory_slugs,
            }
        )
        # Kept out of the public payload; it can contain the owner phone.
        search[str(business.id)] = " ".join(
            filter(
                None,
                [
                    business.name or "",
                    business.short_description or "",
                    business.description or "",
                    business.address or "",
                    " ".join(tags_by_business.get(business.id, [])),
                    owner.full_name or "",
                    owner.phone or "",
                ],
            )
        ).lower()

    return points, search


async def build_snapshot(session: AsyncSession) -> dict:
    points, search = await _load_points(session)
    manifest = {
        "version": CACHE_VERSION,
        "generated_at": _now().isoformat(),
        "points": len(points),
        "mode": "client-clusters",
    }
    return {"manifest": manifest, "points": points, "search": search}


async def _write_snapshot(redis, snapshot: dict) -> None:
    await redis.set(
        SNAPSHOT_KEY,
        json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False),
        ex=CACHE_TTL_SECONDS,
    )


async def rebuild_map_cache(session: AsyncSession, redis) -> dict:
    """Build the full snapshot and persist it. Returns the snapshot."""
    snapshot = await build_snapshot(session)
    try:
        await _write_snapshot(redis, snapshot)
    except Exception:  # noqa: BLE001 - Redis outage must not break the rebuild
        logger.warning("map cache write failed", exc_info=True)
    return snapshot


async def _safe_get(redis, key: str):
    try:
        raw = await redis.get(key)
    except Exception:  # noqa: BLE001 - serve a live build instead
        logger.warning("map cache read failed", exc_info=True)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def _snapshot(session: AsyncSession, redis) -> dict:
    snapshot = await _safe_get(redis, SNAPSHOT_KEY)
    if snapshot is not None:
        return snapshot
    return await rebuild_map_cache(session, redis)


def _matches(
    point: dict,
    search: dict[str, str],
    *,
    category_slug: str | None,
    subcategory_slug: str | None,
    q: str | None,
) -> bool:
    if category_slug:
        category = point.get("category")
        if category is None or category["slug"] != category_slug:
            return False
    if subcategory_slug:
        if subcategory_slug not in (point.get("subcategory_slugs") or []):
            return False
    if q and q not in search.get(point["id"], ""):
        return False
    return True


async def get_map_view(
    session: AsyncSession,
    redis,
    *,
    category_slug: str | None = None,
    subcategory_slug: str | None = None,
    q: str | None = None,
) -> dict:
    """Return every matching point from the cached snapshot.

    Category, subcategory and text filters are applied to the cached rows, so a
    filtered map never re-queries the database.
    """
    snapshot = await _snapshot(session, redis)
    points = snapshot.get("points", [])
    search = snapshot.get("search", {})
    term = (q or "").strip().lower() or None

    if category_slug or subcategory_slug or term:
        points = [
            point
            for point in points
            if _matches(
                point,
                search,
                category_slug=category_slug,
                subcategory_slug=subcategory_slug,
                q=term,
            )
        ]

    return {
        "data": {
            "generated_at": snapshot.get("manifest", {}).get("generated_at"),
            "version": snapshot.get("manifest", {}).get("version", CACHE_VERSION),
            "items": points,
        },
        "meta": {
            "total": len(points),
            "returned": len(points),
            "truncated": len(points) >= MAX_CACHED_POINTS,
            "cached": True,
        },
    }


async def flush_map_cache(redis) -> None:
    """Drop the snapshot and leftover v3 keys; the next request rebuilds."""
    try:
        await redis.delete(SNAPSHOT_KEY, *_LEGACY_KEYS)
    except Exception:  # noqa: BLE001
        logger.warning("map cache flush failed", exc_info=True)


async def cache_status(redis) -> dict:
    snapshot = await _safe_get(redis, SNAPSHOT_KEY)
    if snapshot is None:
        return {
            "ready": False,
            "generated_at": None,
            "points": 0,
            "version": CACHE_VERSION,
            "mode": "client-clusters",
        }
    manifest = snapshot.get("manifest", {})
    return {
        "ready": True,
        "generated_at": manifest.get("generated_at"),
        "points": manifest.get("points", 0),
        "version": manifest.get("version", CACHE_VERSION),
        "mode": manifest.get("mode", "client-clusters"),
    }


async def enqueue_refresh(session: AsyncSession) -> None:
    """Queue a worker rebuild, collapsing bursts into one job per second."""
    from sqlalchemy.exc import IntegrityError

    from app.services.outbox import enqueue

    now = _now()
    key = f"{JOB_TYPE}:{int(now.timestamp())}"
    try:
        async with session.begin_nested():
            await enqueue(
                session,
                job_type=JOB_TYPE,
                payload={},
                run_at=now,
                idempotency_key=key,
            )
    except IntegrityError:
        # Another change in the same second already queued the rebuild.
        pass


async def refresh_from_job(session: AsyncSession, redis) -> dict:
    return await rebuild_map_cache(session, redis)


__all__ = [
    "JOB_TYPE",
    "MAX_CACHED_POINTS",
    "SNAPSHOT_KEY",
    "build_snapshot",
    "cache_status",
    "enqueue_refresh",
    "flush_map_cache",
    "get_map_view",
    "rebuild_map_cache",
    "refresh_from_job",
]
