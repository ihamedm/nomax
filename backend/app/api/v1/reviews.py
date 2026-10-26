import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.business import Business
from app.models.review import Review
from app.models.user import User

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/{review_id}/reply")
async def reply_to_review(
    review_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        rid = uuid.UUID(review_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    review = await session.get(Review, rid)
    if review is None or review.deleted_at is not None:
        raise AppError("not_found", "review_not_found", 404)
    business = await session.get(Business, review.business_id)
    if business is None or business.owner_id != user.id:
        raise AppError("forbidden", "not_business_owner", 403)
    reply = (payload.get("reply") or "").strip()
    if not reply or len(reply) > 250:
        raise AppError("validation_error", "invalid_reply", 422)
    review.reply = reply
    review.replied_at = datetime.now(timezone.utc)
    await session.commit()
    return {"data": {"id": str(review.id), "reply": review.reply}}
