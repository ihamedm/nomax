import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.errors import AppError
from app.db.session import get_db
from app.models.contact import ContactMessage
from app.models.suggestion import CategorySuggestion
from app.models.user import User

router = APIRouter(tags=["utility"])


@router.post("/suggestions/categories")
async def suggest_category(
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    name = (payload.get("name") or payload.get("suggested_name") or "").strip()
    if not name:
        raise AppError("validation_error", "name_required", 422)
    suggestion = CategorySuggestion(
        user_id=user.id,
        type=payload.get("type", "new_subcategory"),
        parent_category_id=payload.get("parent_id") or payload.get("parent_category_id"),
        suggested_name=name,
        description=payload.get("description"),
    )
    session.add(suggestion)
    await session.commit()
    return {"data": {"id": str(suggestion.id), "status": suggestion.status}}


@router.get("/admin/category-suggestions")
async def list_suggestions(
    status: str | None = None,
    actor: User = Depends(require_permissions("category.suggestion.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    stmt = sa.select(CategorySuggestion).where(CategorySuggestion.deleted_at.is_(None))
    if status:
        stmt = stmt.where(CategorySuggestion.status == status)
    rows = (await session.execute(stmt.order_by(CategorySuggestion.created_at.desc()))).scalars().all()
    return {"data": {"items": [
        {"id": str(s.id), "type": s.type, "name": s.suggested_name,
         "description": s.description, "status": s.status}
        for s in rows
    ]}}


@router.patch("/admin/category-suggestions/{suggestion_id}")
async def moderate_suggestion(
    suggestion_id: str,
    payload: dict,
    actor: User = Depends(require_permissions("category.suggestion.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    try:
        sid = uuid.UUID(suggestion_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    suggestion = await session.get(CategorySuggestion, sid)
    if suggestion is None:
        raise AppError("not_found", "suggestion_not_found", 404)
    status = payload.get("status")
    if status not in ("approved", "rejected", "pending"):
        raise AppError("validation_error", "invalid_status", 422)
    suggestion.status = status
    await session.commit()
    return {"data": {"id": str(sid), "status": status}}


@router.post("/contact")
async def create_contact(payload: dict, session: AsyncSession = Depends(get_db)) -> dict:
    name = (payload.get("name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = (payload.get("body") or "").strip()
    if not all((name, phone, subject, body)):
        raise AppError("validation_error", "all_fields_required", 422)
    message = ContactMessage(name=name, phone=phone, subject=subject, body=body)
    session.add(message)
    await session.commit()
    return {"data": {"id": str(message.id)}}


@router.get("/admin/contact-messages")
async def list_contact(
    actor: User = Depends(require_permissions("admin.settings.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    rows = (await session.execute(
        sa.select(ContactMessage).where(ContactMessage.deleted_at.is_(None)).order_by(ContactMessage.created_at.desc())
    )).scalars().all()
    return {"data": {"items": [
        {"id": str(m.id), "name": m.name, "phone": m.phone, "subject": m.subject,
         "body": m.body, "is_read": m.is_read}
        for m in rows
    ]}}
