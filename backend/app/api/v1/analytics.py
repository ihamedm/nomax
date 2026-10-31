from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import User
from app.services import analytics as analytics_service
from app.services import analytics_extra

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


@router.get("/overview")
async def overview(
    days: int = Query(14, ge=7, le=30),
    actor: User = Depends(require_permissions("stats.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    return {"data": await analytics_service.overview(session, days=days)}


@router.get("/quotes")
async def quotes(
    actor: User = Depends(require_permissions("stats.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    return {"data": await analytics_service.quote_analytics(session)}


@router.get("/market")
async def market(
    actor: User = Depends(require_permissions("stats.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    return {"data": await analytics_service.market_analytics(session)}


@router.get("/businesses")
async def businesses(
    actor: User = Depends(require_permissions("stats.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    return {"data": await analytics_extra.business_performance(session)}


@router.get("/map")
async def map_view(
    actor: User = Depends(require_permissions("stats.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    return {"data": await analytics_extra.map_data(session)}


@router.get("/logs/summary")
async def logs_summary(
    days: int = Query(14, ge=7, le=30),
    actor: User = Depends(require_permissions("stats.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    return {"data": await analytics_extra.activity_log_summary(session, days=days)}


@router.get("/logs")
async def logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    type: str | None = Query(None, max_length=40),
    actor: User = Depends(require_permissions("stats.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    result = await analytics_extra.activity_logs(
        session,
        page=page,
        per_page=per_page,
        event_type=type,
    )
    return {"data": {"items": result["items"]}, "meta": result["meta"]}
