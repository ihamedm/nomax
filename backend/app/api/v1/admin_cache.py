"""Dashboard maintenance for the Redis-backed caches.

Exposes the map snapshot and category catalog so an operator can inspect,
flush and rebuild them without touching Redis directly.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import _write_audit
from app.core.deps import require_permissions
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.services import catalog_cache, map_cache

router = APIRouter(prefix="/admin/cache", tags=["admin-cache"])

CACHE_NAMES = ("map", "catalog", "all")


async def _status(redis) -> dict:
    return {
        "map": await map_cache.cache_status(redis),
        "catalog": await catalog_cache.catalog_status(redis),
    }


@router.get("")
async def get_cache_status(
    actor: User = Depends(require_permissions("admin.settings.manage")),
    redis=Depends(get_redis),
) -> dict:
    del actor
    return {"data": await _status(redis)}


@router.post("/{name}/rebuild")
async def rebuild_cache(
    name: str,
    request: Request,
    actor: User = Depends(require_permissions("admin.settings.manage")),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    if name not in CACHE_NAMES:
        raise AppError("not_found", "cache_not_found", 404, {"cache": name})

    if name in ("map", "all"):
        await map_cache.rebuild_map_cache(session, redis)
    if name in ("catalog", "all"):
        await catalog_cache.rebuild_catalog(session, redis)

    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.cache.rebuilt",
        entity_type="cache",
        entity_id=name,
        after={"cache": name},
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return {"data": await _status(redis)}


@router.post("/{name}/flush")
async def flush_cache(
    name: str,
    request: Request,
    actor: User = Depends(require_permissions("admin.settings.manage")),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    if name not in CACHE_NAMES:
        raise AppError("not_found", "cache_not_found", 404, {"cache": name})

    if name in ("map", "all"):
        await map_cache.flush_map_cache(redis)
    if name in ("catalog", "all"):
        await catalog_cache.flush_catalog(redis)

    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.cache.flushed",
        entity_type="cache",
        entity_id=name,
        after={"cache": name},
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return {"data": await _status(redis)}
