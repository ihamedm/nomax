"""Owner-facing review inbox.

Private reviews are visible only here (and to business admins). They never
enter the public moderation queue, so they have no approve action.
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.business import Business
from app.models.review import Review
from app.models.user import User

router = APIRouter(tags=["owner-reviews"])

OWNER_VISIBLE_STATUSES = ("pending", "private", "approved")
OWNER_UNREAD_STATUSES = ("pending", "private")


def _owner_review_payload(review: Review, business: Business) -> dict:
    return {
        "id": str(review.id),
        "business_id": str(business.id),
        "business_name": business.name,
        "business_slug": business.slug,
        "rating": review.rating,
        "text": review.text,
        "author_name": review.author_name,
        "status": review.status,
        "is_private": review.is_private,
        "reply": review.reply,
        "replied_at": review.replied_at.isoformat() if review.replied_at else None,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


def _owner_visible_filter(owner_id: uuid.UUID) -> tuple:
    return (
        Business.owner_id == owner_id,
        Business.deleted_at.is_(None),
        Review.deleted_at.is_(None),
        Review.status.in_(OWNER_VISIBLE_STATUSES),
    )


async def _unread_count(session: AsyncSession, owner_id: uuid.UUID) -> int:
    return int(
        (
            await session.execute(
                sa.select(sa.func.count(Review.id))
                .join(Business, Review.business_id == Business.id)
                .where(
                    Business.owner_id == owner_id,
                    Business.deleted_at.is_(None),
                    Review.deleted_at.is_(None),
                    Review.status.in_(OWNER_UNREAD_STATUSES),
                    Review.owner_seen_at.is_(None),
                )
            )
        ).scalar()
        or 0
    )


@router.get("/me/reviews")
async def list_owner_reviews(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await session.execute(
            sa.select(Review, Business)
            .join(Business, Review.business_id == Business.id)
            .where(*_owner_visible_filter(user.id))
            .order_by(Review.created_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "data": {
            "items": [
                _owner_review_payload(review, business) for review, business in rows
            ],
            "unread_count": await _unread_count(session, user.id),
        }
    }


@router.get("/me/reviews/unread-count")
async def owner_review_unread_count(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return {"data": {"count": await _unread_count(session, user.id)}}


@router.patch("/me/reviews/mark-seen")
@router.post("/me/reviews/mark-seen")
async def mark_owner_reviews_seen(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    reviews = (
        await session.execute(
            sa.select(Review)
            .join(Business, Review.business_id == Business.id)
            .where(
                Business.owner_id == user.id,
                Business.deleted_at.is_(None),
                Review.deleted_at.is_(None),
                Review.status.in_(OWNER_UNREAD_STATUSES),
                Review.owner_seen_at.is_(None),
            )
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for review in reviews:
        review.owner_seen_at = now
    await session.commit()
    return {"data": {"updated": len(reviews), "unread_count": 0}}
