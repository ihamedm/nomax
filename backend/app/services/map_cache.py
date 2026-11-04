"""Pre-computed map snapshot with zoom-dependent clustering.

Approved businesses that have coordinates are materialised once into Redis as a
small "pyramid":

* ``map:v1:points``           – flat list of business markers used at detail zooms
* ``map:v1:clusters:{zoom}``  – grid clusters for zoom 6..14
* ``map:v1:manifest``         – build timestamp and counts

The snapshot is rebuilt by a worker job after a business changes state and on
demand from the dashboard. A cold cache is filled synchronously on the first
map request, so the map never depends on the worker being up.

Clustering is a plain lat/lng grid whose cell size halves with each zoom level
(``360 / 2**zoom`` degrees, i.e. one Web-Mercator tile). That is the same idea
used by server-side clustering endpoints (Mapbox/Google/Leaflet.markercluster)
but is computed once per rebuild instead of per request.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory

logger = logging.getLogger("nomax.map_cache")

CACHE_VERSION = 1
MANIFEST_KEY = f"map:v{CACHE_VERSION}:manifest"
POINTS_KEY = f"map:v{CACHE_VERSION}:points"
CLUSTERS_KEY = f"map:v{CACHE_VERSION}:clusters:{{zoom}}"

MIN_CLUSTER_ZOOM = 6
MAX_CLUSTER_ZOOM = 14
DETAIL_ZOOM = 15

MAX_POINTS_IN_RESPONSE = 300
MAX_CLUSTERS_IN_RESPONSE = 400
MAX_CACHED_POINTS = 5000

# Keeps a stale snapshot from living forever if the worker never runs.
CACHE_TTL_SECONDS = 7 * 24 * 3600

JOB_TYPE = "map_cache.refresh"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cell_size(zoom: int) -> float:
    """Grid cell size in degrees for a zoom level (one Web-Mercator tile)."""
    return 360.0 / (2 ** zoom)


def _category_ref(category: Category | None) -> dict | None:
    if category is None:
        return None
    return {
        "id": category.id,
        "slug": category.slug,
        "name": category.name,
        "icon": category.icon,
    }


async def _load_points(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            sa.select(Business, Category, Subcategory)
            .join(Category, Business.category_id == Category.id)
            .outerjoin(Subcategory, Business.subcategory_id == Subcategory.id)
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

    points: list[dict] = []
    for business, category, subcategory in rows:
        points.append(
            {
                "id": str(business.id),
                "slug": business.slug,
                "name": business.name,
                "lat": round(float(business.geo_lat), 6),
                "lng": round(float(business.geo_lng), 6),
                "address": business.address,
                "short_description": business.short_description,
                "rating_avg": round(business.rating_avg or 0, 2),
                "rating_count": business.rating_count or 0,
                "is_24h": business.is_24h,
                "is_verified": business.is_verified,
                "profile_image_url": business.profile_image_url,
                "category": _category_ref(category),
                "subcategory": (
                    _category_ref(subcategory)
                    if subcategory is not None and subcategory.deleted_at is None
                    else None
                ),
                # Lower-cased haystack so a filtered map view can reuse the cache
                # instead of re-querying the database per keystroke.
                "search_text": " ".join(
                    filter(
                        None,
                        [
                            business.name or "",
                            business.short_description or "",
                            business.address or "",
                        ],
                    )
                ).lower(),
            }
        )
    return points


def build_clusters(points: list[dict], zoom: int) -> list[dict]:
    """Bucket points into a lat/lng grid and emit one cluster per occupied cell."""
    size = cell_size(zoom)
    buckets: dict[tuple[int, int], dict] = {}

    for point in points:
        key = (math.floor(point["lat"] / size), math.floor(point["lng"] / size))
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = {
                "lat_sum": point["lat"],
                "lng_sum": point["lng"],
                "count": 1,
            }
        else:
            bucket["lat_sum"] += point["lat"]
            bucket["lng_sum"] += point["lng"]
            bucket["count"] += 1

    clusters: list[dict] = []
    for (row, column), bucket in buckets.items():
        count = bucket["count"]
        clusters.append(
            {
                "id": f"z{zoom}:{row}:{column}",
                "lat": round(bucket["lat_sum"] / count, 6),
                "lng": round(bucket["lng_sum"] / count, 6),
                "count": count,
            }
        )
    clusters.sort(key=lambda item: (-item["count"], item["id"]))
    return clusters


async def build_snapshot(session: AsyncSession) -> dict:
    points = await _load_points(session)
    clusters = {
        zoom: build_clusters(points, zoom)
        for zoom in range(MIN_CLUSTER_ZOOM, MAX_CLUSTER_ZOOM + 1)
    }
    manifest = {
        "version": CACHE_VERSION,
        "generated_at": _now().isoformat(),
        "points": len(points),
        "cluster_zooms": [MIN_CLUSTER_ZOOM, MAX_CLUSTER_ZOOM],
        "detail_zoom": DETAIL_ZOOM,
        "counts": {str(zoom): len(items) for zoom, items in clusters.items()},
    }
    return {"manifest": manifest, "points": points, "clusters": clusters}


async def _write_snapshot(redis, snapshot: dict) -> None:
    manifest = snapshot["manifest"]
    await redis.set(
        POINTS_KEY, json.dumps(snapshot["points"], separators=(",", ":")), ex=CACHE_TTL_SECONDS
    )
    for zoom, clusters in snapshot["clusters"].items():
        await redis.set(
            CLUSTERS_KEY.format(zoom=zoom),
            json.dumps(clusters, separators=(",", ":")),
            ex=CACHE_TTL_SECONDS,
        )
    await redis.set(MANIFEST_KEY, json.dumps(manifest), ex=CACHE_TTL_SECONDS)


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


def _in_bbox(lat: float, lng: float, bbox: tuple[float, float, float, float], margin: float) -> bool:
    west, south, east, north = bbox
    return (
        south - margin <= lat <= north + margin
        and west - margin <= lng <= east + margin
    )


def _matches(
    point: dict,
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
        subcategory = point.get("subcategory")
        if subcategory is None or subcategory["slug"] != subcategory_slug:
            return False
    if q:
        if q.strip().lower() not in point.get("search_text", ""):
            return False
    return True


async def _manifest_and_points(session: AsyncSession, redis) -> tuple[dict, list[dict]]:
    manifest = await _safe_get(redis, MANIFEST_KEY)
    if manifest is not None:
        points = await _safe_get(redis, POINTS_KEY)
        if points is not None:
            return manifest, points
    snapshot = await rebuild_map_cache(session, redis)
    return snapshot["manifest"], snapshot["points"]


async def get_map_view(
    session: AsyncSession,
    redis,
    *,
    zoom: int,
    bbox: tuple[float, float, float, float] | None = None,
    category_slug: str | None = None,
    subcategory_slug: str | None = None,
    q: str | None = None,
) -> dict:
    """Return clusters (low zoom) or individual business markers (detail zoom).

    Unfiltered low-zoom requests read the pre-computed cluster list straight
    from Redis. When a search/category filter is active the cached points are
    re-bucketed in memory, so filtering never hits the database.
    """
    detail = zoom >= DETAIL_ZOOM
    cluster_zoom = min(max(zoom, MIN_CLUSTER_ZOOM), MAX_CLUSTER_ZOOM)
    filtered = bool(category_slug or subcategory_slug or q)

    if detail:
        manifest, rows = await _manifest_and_points(session, redis)
        if filtered:
            rows = [
                point
                for point in rows
                if _matches(
                    point,
                    category_slug=category_slug,
                    subcategory_slug=subcategory_slug,
                    q=q,
                )
            ]
        if bbox is not None:
            rows = [item for item in rows if _in_bbox(item["lat"], item["lng"], bbox, 0.0)]
        total = len(rows)
        truncated = total > MAX_POINTS_IN_RESPONSE
        rows = rows[:MAX_POINTS_IN_RESPONSE]
        return {
            "data": {
                "mode": "points",
                "zoom": zoom,
                "generated_at": manifest.get("generated_at"),
                "items": rows,
                "clusters": [],
            },
            "meta": {
                "total": total,
                "returned": len(rows),
                "truncated": truncated,
                "cached": True,
            },
        }

    if filtered:
        manifest, points = await _manifest_and_points(session, redis)
        points = [
            point
            for point in points
            if _matches(
                point,
                category_slug=category_slug,
                subcategory_slug=subcategory_slug,
                q=q,
            )
        ]
        clusters = build_clusters(points, cluster_zoom)
    else:
        manifest = await _safe_get(redis, MANIFEST_KEY)
        clusters = (
            await _safe_get(redis, CLUSTERS_KEY.format(zoom=cluster_zoom))
            if manifest is not None
            else None
        )
        if clusters is None:
            snapshot = await rebuild_map_cache(session, redis)
            manifest = snapshot["manifest"]
            clusters = snapshot["clusters"][cluster_zoom]

    if bbox is not None:
        # Clusters are cell centroids; pad by half a cell so members sitting
        # just outside the viewport still surface on screen edges.
        margin = cell_size(cluster_zoom) * 0.5
        clusters = [item for item in clusters if _in_bbox(item["lat"], item["lng"], bbox, margin)]
    total = sum(item["count"] for item in clusters)
    truncated = len(clusters) > MAX_CLUSTERS_IN_RESPONSE
    clusters = clusters[:MAX_CLUSTERS_IN_RESPONSE]
    return {
        "data": {
            "mode": "clusters",
            "zoom": zoom,
            "generated_at": manifest.get("generated_at"),
            "items": [],
            "clusters": clusters,
        },
        "meta": {
            "total": total,
            "returned": len(clusters),
            "truncated": truncated,
            "cached": True,
        },
    }


async def flush_map_cache(redis) -> None:
    """Drop every snapshot key; the next map request rebuilds on demand."""
    keys = [MANIFEST_KEY, POINTS_KEY] + [
        CLUSTERS_KEY.format(zoom=zoom)
        for zoom in range(MIN_CLUSTER_ZOOM, MAX_CLUSTER_ZOOM + 1)
    ]
    try:
        await redis.delete(*keys)
    except Exception:  # noqa: BLE001
        logger.warning("map cache flush failed", exc_info=True)


async def cache_status(redis) -> dict:
    manifest = await _safe_get(redis, MANIFEST_KEY)
    if manifest is None:
        return {"ready": False, "generated_at": None, "points": 0, "counts": {}}
    return {
        "ready": True,
        "generated_at": manifest.get("generated_at"),
        "points": manifest.get("points", 0),
        "counts": manifest.get("counts", {}),
        "detail_zoom": manifest.get("detail_zoom", DETAIL_ZOOM),
        "cluster_zooms": manifest.get("cluster_zooms", [MIN_CLUSTER_ZOOM, MAX_CLUSTER_ZOOM]),
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
    "build_clusters",
    "build_snapshot",
    "cache_status",
    "cell_size",
    "enqueue_refresh",
    "flush_map_cache",
    "get_map_view",
    "rebuild_map_cache",
    "refresh_from_job",
]
