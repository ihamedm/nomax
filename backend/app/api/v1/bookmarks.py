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
            sa.select(Business, Bookmark.note)
            .join(Bookmark, Bookmark.business_id == Business.id)
            .where(
                Bookmark.user_id == user.id,
                Business.deleted_at.is_(None),
                Business.status == BusinessStatus.APPROVED,
            )
            .order_by(Bookmark.created_at.desc())
        )
    ).all()
    items = []
    for business, note in rows:
        item = _business_payload(BusinessHit(business=business))
        item["bookmark_note"] = note
        items.append(item)
    return {"data": {"items": items}}


@router.post("/me/bookmarks/{business_id}")
async def save_business(
    business_id: str,
    payload: dict | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    data = payload or {}
    note = (data.get("note") or "").strip() or None
    if note is not None and len(note) > 300:
        raise AppError("validation_error", "bookmark_note_too_long", 422)
    business = await _get_business(session, business_id)
    existing = (
        await session.execute(
            sa.select(Bookmark).where(
                Bookmark.user_id == user.id, Bookmark.business_id == business.id
            )
        )
    ).scalars().first()
    if existing is None:
        session.add(Bookmark(user_id=user.id, business_id=business.id, note=note))
        await session.commit()
    elif "note" in data and existing.note != note:
        existing.note = note
        await session.commit()
    return {"data": {"saved": True, "note": note}}


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
