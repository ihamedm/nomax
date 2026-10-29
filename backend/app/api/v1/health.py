import logging

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.session import get_db
from app.services.storage import health as storage_health

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"data": {"status": "ok"}}


@router.get("/ready")
async def ready(
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    checks: dict[str, str] = {}

    try:
        await session.execute(sa.text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness must never raise
        logger.warning("readiness database check failed: %s", exc)
        checks["database"] = "error"

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness redis check failed: %s", exc)
        checks["redis"] = "error"

    checks["storage"] = await storage_health()

    if any(value not in ("ok", "not_configured") for value in checks.values()):
        return JSONResponse(
            status_code=503,
            content={
                "data": {"status": "degraded", "checks": checks},
                "error": {"code": "not_ready", "message": "dependencies_unavailable"},
            },
        )

    return {"data": {"status": "ok", "checks": checks}}
