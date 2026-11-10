import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.businesses import _business_payload
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.bookmark import Bookmark
from app.models.business import Business, BusinessStatus
from app.models.user import User
from app.services.business_search import BusinessHit

router = APIRouter(tags=["bookmarks"])


async def _get_business(session: AsyncSession, business_id: str) -> Business:
    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if (
        business is None
        or business.deleted_at is not None
        or business.status != BusinessStatus.APPROVED
    ):
        raise AppError("not_found", "business_not_found", 404)
    return business


@router.get("/me/bookmarks")
async def list_bookmarks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await session.execute(
            sa.select(Business)
            .join(Bookmark, Bookmark.business_id == Business.id)
            .where(
                Bookmark.user_id == user.id,
                Business.deleted_at.is_(None),
                Business.status == BusinessStatus.APPROVED,
            )
            .order_by(Bookmark.created_at.desc())
        )
    ).scalars().all()
    return {"data": {"items": [_business_payload(BusinessHit(business=b)) for b in rows]}}


@router.post("/me/bookmarks/{business_id}")
async def save_business(
    business_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    business = await _get_business(session, business_id)
    existing = (
        await session.execute(
            sa.select(Bookmark).where(
                Bookmark.user_id == user.id, Bookmark.business_id == business.id
            )
        )
    ).scalars().first()
    if existing is None:
        session.add(Bookmark(user_id=user.id, business_id=business.id))
        await session.commit()
    return {"data": {"saved": True}}


@router.delete("/me/bookmarks/{business_id}")
async def remove_bookmark(
    business_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    business = await _get_business(session, business_id)
    existing = (
        await session.execute(
            sa.select(Bookmark).where(
                Bookmark.user_id == user.id, Bookmark.business_id == business.id
            )
        )
    ).scalars().first()
    if existing is not None:
        await session.delete(existing)
        await session.commit()
    return {"data": {"saved": False}}
