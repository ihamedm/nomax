import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.errors import AppError
from app.db.session import get_db
from app.models.admin import AuditLog
from app.models.notification import DeviceToken, Notification, NotificationDelivery
from app.models.user import User, UserRole
from app.services.inapp_notifications import (
    AUDIENCES,
    broadcast,
    serialize_notification,
    unread_count,
)

router = APIRouter(tags=["notifications"])


@router.post("/devices")
async def register_device(
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    provider = payload.get("provider")
    token = payload.get("token")
    if not provider or not token:
        raise AppError("validation_error", "provider_and_token_required", 422)
    existing = (
        await session.execute(
            sa.select(DeviceToken).where(
                DeviceToken.provider == provider, DeviceToken.token == token
            )
        )
    ).scalars().first()
    if existing:
        existing.user_id = user.id
        existing.is_active = True
        await session.commit()
        return {"data": {"id": str(existing.id)}}
    device = DeviceToken(
        user_id=user.id,
        provider=provider,
        token=token,
        platform=payload.get("platform", "android"),
        app_version=payload.get("app_version"),
    )
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return {"data": {"id": str(device.id)}}


@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        did = uuid.UUID(device_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    device = await session.get(DeviceToken, did)
    if device is None or device.user_id != user.id:
        raise AppError("not_found", "device_not_found", 404)
    device.is_active = False
    await session.commit()
    return {"data": {"id": str(device.id), "is_active": False}}


async def _unread_count_response(session: AsyncSession, user: User) -> dict:
    return {"data": {"count": await unread_count(session, user.id)}}


@router.get("/notifications")
@router.get("/me/notifications")
async def list_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    items = (
        await session.execute(
            sa.select(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.deleted_at.is_(None),
            )
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return {
        "data": {
            "items": [serialize_notification(notification) for notification in items],
            "unread_count": await unread_count(session, user.id),
        }
    }


@router.get("/notifications/unread-count")
@router.get("/me/notifications/unread-count")
async def get_unread_count(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await _unread_count_response(session, user)


@router.patch("/notifications/read-all")
@router.patch("/me/notifications/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await session.execute(
        sa.update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
            Notification.deleted_at.is_(None),
        )
        .values(is_read=True)
    )
    await session.commit()
    return {"data": {"updated": result.rowcount or 0, "unread_count": 0}}


@router.get("/admin/notification-deliveries")
async def list_deliveries(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise AppError("forbidden", "admin_required", 403)
    items = (
        await session.execute(
            sa.select(NotificationDelivery).order_by(NotificationDelivery.id).limit(100)
        )
    ).scalars().all()
    return {
        "data": {
            "items": [
                {
                    "id": str(d.id),
                    "notification_id": str(d.notification_id),
                    "provider": d.provider,
                    "status": d.status,
                    "error": d.error,
                    "sent_at": d.sent_at.isoformat() if d.sent_at else None,
                }
                for d in items
            ]
        }
    }


@router.post("/admin/notifications/broadcast")
async def broadcast_notification(
    payload: dict,
    user: User = Depends(require_permissions("notification.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or "").strip()
    if not title:
        raise AppError("validation_error", "title_required", 422)
    if len(title) > 160:
        raise AppError("validation_error", "title_too_long", 422)
    if not body:
        raise AppError("validation_error", "body_required", 422)
    if len(body) > 4000:
        raise AppError("validation_error", "body_too_long", 422)

    audience = payload.get("audience") or "all"
    if audience not in AUDIENCES:
        raise AppError("validation_error", "invalid_audience", 422)

    receiver_id: uuid.UUID | None = None
    if audience == "user":
        raw_user_id = payload.get("user_id")
        if not raw_user_id:
            raise AppError("user_id_required", "user_id_required", 422)
        try:
            receiver_id = uuid.UUID(str(raw_user_id))
        except ValueError:
            raise AppError("validation_error", "invalid_user_id", 422)
        receiver = await session.get(User, receiver_id)
        if receiver is None or receiver.deleted_at is not None:
            raise AppError("not_found", "user_not_found", 404)

    action_url = (payload.get("action_url") or "").strip() or None
    if action_url and (not action_url.startswith("/") or action_url.startswith("//")):
        raise AppError("validation_error", "invalid_action_url", 422)

    sent = await broadcast(
        session,
        title=title,
        body=body,
        audience=audience,
        user_id=receiver_id,
        action_url=action_url,
    )
    session.add(
        AuditLog(
            actor_id=user.id,
            action="notification.broadcast",
            entity_type="notification",
            entity_id=None,
            after={"audience": audience, "sent": sent, "title": title},
        )
    )
    await session.commit()
    return {"data": {"sent": sent, "audience": audience}}


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        nid = uuid.UUID(notification_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    notification = await session.get(Notification, nid)
    if notification is None or notification.user_id != user.id:
        raise AppError("not_found", "notification_not_found", 404)
    notification.is_read = True
    await session.commit()
    await session.refresh(notification)
    return {
        "data": {
            "id": str(notification.id),
            "is_read": True,
            "unread_count": await unread_count(session, user.id),
        }
    }
