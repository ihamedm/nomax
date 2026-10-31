"""In-app message center.

These messages are stored per receiver (`Notification.user_id`) and shown inside
the app. They are intentionally separate from `DeviceToken` /
`NotificationDelivery`, which drive OS push delivery.
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User, UserRole

TYPE_BUSINESS_APPROVED = "business_approved"
TYPE_BUSINESS_REJECTED = "business_rejected"
TYPE_QUOTE_REQUEST = "quote_request"
TYPE_QUOTE_OFFER = "quote_offer"
TYPE_QUOTE_ACCEPTED = "quote_accepted"
TYPE_QUOTE_CANCELLED = "quote_cancelled"
TYPE_ANNOUNCEMENT = "announcement"
TYPE_SYSTEM = "system"

AUDIENCES = ("all", "owners", "customers", "user")


def serialize_notification(notification: Notification) -> dict:
    return {
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title,
        "body": notification.body,
        "payload": notification.payload or {},
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }


async def notify_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    title: str,
    body: str,
    type: str = TYPE_SYSTEM,
    payload: dict | None = None,
) -> Notification:
    """Queue one in-app message for a single receiver (the user id)."""
    notification = Notification(
        user_id=user_id,
        title=title[:160],
        body=body,
        type=type,
        payload=payload or {},
    )
    session.add(notification)
    return notification


async def notify_business_rejected(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    business_id: uuid.UUID,
    business_name: str,
    reason: str | None,
) -> Notification:
    reason_text = (reason or "").strip() or "دلیل رد شدن کسب‌وکار مشخص نشده است."
    return await notify_user(
        session,
        owner_id,
        type=TYPE_BUSINESS_REJECTED,
        title=f"کسب‌وکار «{business_name}» رد شد",
        body=(
            f"دلیل: {reason_text}\n"
            "می‌توانید اطلاعات کسب‌وکار را اصلاح کنید و دوباره برای بررسی ارسال کنید."
        ),
        payload={
            "business_id": str(business_id),
            "business_name": business_name,
            "rejection_reason": reason_text,
            "action": "edit_business",
            "action_url": f"/businesses/{business_id}/edit",
        },
    )


async def notify_business_approved(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    business_id: uuid.UUID,
    business_slug: str,
    business_name: str,
) -> Notification:
    return await notify_user(
        session,
        owner_id,
        type=TYPE_BUSINESS_APPROVED,
        title=f"کسب‌وکار «{business_name}» تأیید شد",
        body="کسب‌وکار شما اکنون در نومکس برای مشتریان نمایش داده می‌شود.",
        payload={
            "business_id": str(business_id),
            "business_slug": business_slug,
            "business_name": business_name,
            "action": "view_business",
            "action_url": f"/businesses/{business_slug}",
        },
    )


async def notify_quote_request(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    quote_id: uuid.UUID,
    title: str,
    is_urgent: bool,
) -> Notification:
    return await notify_user(
        session,
        owner_id,
        type=TYPE_QUOTE_REQUEST,
        title="درخواست قیمت جدید",
        body=f"«{title[:80]}»" + (" — فوری" if is_urgent else ""),
        payload={
            "quote_id": str(quote_id),
            "action": "view_quote_request",
            "action_url": "/me/customers",
        },
    )


async def notify_quote_offer(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    quote_id: uuid.UUID,
    business_name: str,
    price: float | None,
) -> Notification:
    price_text = f"{int(price):,} تومان" if price is not None else "قیمت نامشخص"
    return await notify_user(
        session,
        customer_id,
        type=TYPE_QUOTE_OFFER,
        title="پیشنهاد قیمت جدید",
        body=f"{business_name[:80]} برای درخواست شما پیشنهاد {price_text} ثبت کرد.",
        payload={
            "quote_id": str(quote_id),
            "action": "view_quote",
            "action_url": f"/quote/mine/{quote_id}",
        },
    )


async def notify_quote_accepted(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    quote_id: uuid.UUID,
    business_name: str,
) -> Notification:
    return await notify_user(
        session,
        owner_id,
        type=TYPE_QUOTE_ACCEPTED,
        title="پیشنهاد شما پذیرفته شد",
        body=f"مشتری پیشنهاد «{business_name[:80]}» را برای درخواست قیمت انتخاب کرد.",
        payload={
            "quote_id": str(quote_id),
            "action": "view_customer",
            "action_url": "/me/customers",
        },
    )


async def notify_quote_cancelled(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    quote_id: uuid.UUID,
    title: str,
) -> Notification:
    return await notify_user(
        session,
        owner_id,
        type=TYPE_QUOTE_CANCELLED,
        title="درخواست قیمت لغو شد",
        body=f"درخواست «{title[:80]}» لغو شد.",
        payload={
            "quote_id": str(quote_id),
            "action": "view_quote_request",
            "action_url": "/me/customers",
        },
    )


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        (
            await session.execute(
                sa.select(sa.func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.is_read.is_(False),
                    Notification.deleted_at.is_(None),
                )
            )
        ).scalar()
        or 0
    )


async def broadcast(
    session: AsyncSession,
    *,
    title: str,
    body: str,
    audience: str = "all",
    user_id: uuid.UUID | None = None,
    action_url: str | None = None,
) -> int:
    """Create one in-app message per receiver and return how many were queued."""
    if audience not in AUDIENCES:
        raise ValueError("invalid_audience")

    if audience == "user":
        if user_id is None:
            raise ValueError("user_id_required")
        receiver_ids = [user_id]
    else:
        stmt = sa.select(User.id).where(User.deleted_at.is_(None))
        if audience == "owners":
            stmt = stmt.where(User.role == UserRole.OWNER)
        elif audience == "customers":
            stmt = stmt.where(User.role == UserRole.CUSTOMER)
        receiver_ids = list((await session.execute(stmt)).scalars().all())

    payload: dict = {"action": "announcement"}
    if action_url:
        payload["action_url"] = action_url

    for receiver_id in receiver_ids:
        await notify_user(
            session,
            receiver_id,
            type=TYPE_ANNOUNCEMENT,
            title=title,
            body=body,
            payload=payload,
        )
    return len(receiver_ids)
