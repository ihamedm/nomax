"""Redis cache for the public category catalog.

The catalog is small, read on every page load and changes rarely, so it is a
good fit for an explicit cache with direct invalidation from the CMS endpoints.
A cold cache is filled on first read; admins can inspect/flush/rebuild it from
the dashboard cache page.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, Subcategory

logger = logging.getLogger("nomax.catalog_cache")

CACHE_VERSION = 1
CATEGORIES_KEY = f"catalog:v{CACHE_VERSION}:categories"
SUBCATEGORIES_KEY = f"catalog:v{CACHE_VERSION}:subcategories"
META_KEY = f"catalog:v{CACHE_VERSION}:meta"

CACHE_TTL_SECONDS = 12 * 3600


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def build_catalog(session: AsyncSession) -> dict:
    categories = (
        (
            await session.execute(
                sa.select(Category)
                .where(Category.deleted_at.is_(None), Category.is_active.is_(True))
                .order_by(Category.sort_order, Category.id)
            )
        )
        .scalars()
        .all()
    )
    rows = (
        (
            await session.execute(
                sa.select(Subcategory, Category)
                .join(Category, Subcategory.category_id == Category.id)
                .where(
                    Subcategory.deleted_at.is_(None),
                    Category.deleted_at.is_(None),
                    Category.is_active.is_(True),
                )
                .order_by(Category.sort_order, Subcategory.sort_order, Subcategory.id)
            )
        )
        .all()
    )

    counts: dict[int, int] = {}
    subcategories: list[dict] = []
    for subcategory, category in rows:
        counts[category.id] = counts.get(category.id, 0) + 1
        subcategories.append(
            {
                "id": subcategory.id,
                "category_id": subcategory.category_id,
                "slug": subcategory.slug,
                "name": subcategory.name,
                "icon": subcategory.icon,
                "sort_order": subcategory.sort_order,
                "standard_tags": list(subcategory.standard_tags or []),
                "category": {
                    "id": category.id,
                    "slug": category.slug,
                    "name": category.name,
                    "icon": category.icon,
                },
            }
        )

    return {
        "categories": [
            {
                "id": category.id,
                "slug": category.slug,
                "name": category.name,
                "icon": category.icon,
                "sort_order": category.sort_order,
                "subcategory_count": counts.get(category.id, 0),
            }
            for category in categories
        ],
        "subcategories": subcategories,
        "meta": {
            "version": CACHE_VERSION,
            "generated_at": _now().isoformat(),
            "categories": len(categories),
            "subcategories": len(subcategories),
        },
    }


async def _write(redis, catalog: dict) -> None:
    await redis.set(
        CATEGORIES_KEY,
        json.dumps(catalog["categories"], separators=(",", ":")),
        ex=CACHE_TTL_SECONDS,
    )
    await redis.set(
        SUBCATEGORIES_KEY,
        json.dumps(catalog["subcategories"], separators=(",", ":")),
        ex=CACHE_TTL_SECONDS,
    )
    await redis.set(META_KEY, json.dumps(catalog["meta"]), ex=CACHE_TTL_SECONDS)


async def rebuild_catalog(session: AsyncSession, redis) -> dict:
    catalog = await build_catalog(session)
    try:
        await _write(redis, catalog)
    except Exception:  # noqa: BLE001 - Redis outage must not break the catalog
        logger.warning("catalog cache write failed", exc_info=True)
    return catalog


async def _safe_get(redis, key: str):
    try:
        raw = await redis.get(key)
    except Exception:  # noqa: BLE001
        logger.warning("catalog cache read failed", exc_info=True)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def ensure_catalog(session: AsyncSession, redis) -> dict:
    """Return the cached catalog, building and persisting it when missing."""
    categories = await _safe_get(redis, CATEGORIES_KEY)
    subcategories = await _safe_get(redis, SUBCATEGORIES_KEY)
    meta = await _safe_get(redis, META_KEY)
    if categories is not None and subcategories is not None:
        return {
            "categories": categories,
            "subcategories": subcategories,
            "meta": meta or {},
        }
    return await rebuild_catalog(session, redis)


async def invalidate_catalog(redis) -> None:
    try:
        await redis.delete(CATEGORIES_KEY, SUBCATEGORIES_KEY, META_KEY)
    except Exception:  # noqa: BLE001
        logger.warning("catalog cache invalidation failed", exc_info=True)


async def flush_catalog(redis) -> None:
    await invalidate_catalog(redis)


async def catalog_status(redis) -> dict:
    meta = await _safe_get(redis, META_KEY)
    if meta is None:
        return {"ready": False, "generated_at": None, "categories": 0, "subcategories": 0}
    return {"ready": True, **meta}
