from fastapi import APIRouter, Depends
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.ad import Ad
from app.models.user import User

router = APIRouter(prefix="/ads", tags=["ads"])


@router.get("")
async def list_ads(session: AsyncSession = Depends(get_db)) -> dict:
    rows = (
        await session.execute(sa.select(Ad).where(Ad.is_active.is_(True), Ad.deleted_at.is_(None)))
    ).scalars().all()
    return {"data": {"items": [
        {"id": str(a.id), "title": a.title, "image_url": a.image_url,
         "target_url": a.target_url, "body": a.body}
        for a in rows
    ]}}


@router.post("")
async def create_ad(
    payload: dict,
    user: User = Depends(require_permissions("ad.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del user
    ad = Ad(title=payload.get("title", ""), image_url=payload.get("image_url"),
            target_url=payload.get("target_url"), body=payload.get("body"),
            placement=payload.get("placement", "home_banner"),
            starts_at=payload.get("starts_at"), ends_at=payload.get("ends_at"))
    session.add(ad)
    await session.commit()
    await session.refresh(ad)
    return {"data": {"id": str(ad.id)}}
