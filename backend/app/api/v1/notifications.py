import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.notification import DeviceToken, Notification, NotificationDelivery
from app.models.user import User, UserRole

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


@router.get("/notifications")
async def list_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    items = (
        await session.execute(
            sa.select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return {
        "data": {
            "items": [
                {
                    "id": str(n.id),
                    "title": n.title,
                    "body": n.body,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in items
            ]
        }
    }


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
    return {"data": {"id": str(notification.id), "is_read": True}}
