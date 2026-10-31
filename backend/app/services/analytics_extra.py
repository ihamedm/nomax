"""Business performance, map data and user activity logs for analytics."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import QuoteDelivery, SearchLog
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.quote import Offer, QuoteRequest
from app.models.review import Review
from app.models.user import User
from app.services.analytics import (
    as_utc,
    local_date,
    start_of_day_utc,
    today_local,
)
from app.services.quote_service import category_payload, subcategory_payload

EVENT_TYPES = (
    "search",
    "user_registered",
    "business_created",
    "review_created",
    "quote_requested",
    "quote_offer",
    "quote_seen",
    "quote_chosen",
)


def _rate(part: int, total: int) -> float:
    return round((part / total) * 100, 1) if total else 0


async def _count(session: AsyncSession, stmt) -> int:
    return int((await session.execute(stmt)).scalar() or 0)


async def business_performance(session: AsyncSession) -> dict:
    businesses = (
        await session.execute(
            sa.select(Business)
            .where(
                Business.deleted_at.is_(None),
                Business.status == BusinessStatus.APPROVED,
            )
            .order_by(Business.view_count.desc(), Business.name)
        )
    ).scalars().all()

    offer_counts = {
        business_id: {"suggested": int(suggested or 0), "accepted": int(accepted or 0)}
        for business_id, suggested, accepted in (
            await session.execute(
                sa.select(
                    Offer.business_id,
                    sa.func.count(Offer.id),
                    sa.func.sum(sa.case((Offer.status == "accepted", 1), else_=0)),
                )
                .where(Offer.deleted_at.is_(None), Offer.status != "declined")
                .group_by(Offer.business_id)
            )
        ).all()
    }
    delivery_counts = dict(
        (
            await session.execute(
                sa.select(QuoteDelivery.business_id, sa.func.count(QuoteDelivery.id))
                .group_by(QuoteDelivery.business_id)
            )
        ).all()
    )
    review_stats = {
        business_id: {"total": int(total or 0), "negative": int(negative or 0)}
        for business_id, total, negative in (
            await session.execute(
                sa.select(
                    Review.business_id,
                    sa.func.count(Review.id),
                    sa.func.sum(sa.case((Review.rating <= 2, 1), else_=0)),
                )
                .where(
                    Review.deleted_at.is_(None),
                    Review.is_private.is_(False),
                    Review.status == "approved",
                )
                .group_by(Review.business_id)
            )
        ).all()
    }

    rows = []
    for business in businesses:
        offers = offer_counts.get(business.id, {"suggested": 0, "accepted": 0})
        deliveries = int(delivery_counts.get(business.id, 0))
        reviews = review_stats.get(business.id, {"total": 0, "negative": 0})
        response_base = max(deliveries, offers["suggested"])
        response_rate = _rate(offers["suggested"], response_base)
        negative_rate = _rate(reviews["negative"], reviews["total"])
        rating = round(business.rating_avg or 0, 2)

        if (
            reviews["total"] >= 3
            and (negative_rate >= 40 or rating < 3)
        ) or (reviews["total"] >= 2 and negative_rate >= 50):
            status, status_label = "critical", "بحرانی — نظرات منفی"
        elif reviews["total"] >= 1 and (negative_rate >= 50 or rating < 3):
            status, status_label = "watch", "نیازمند بررسی"
        elif response_base >= 3 and response_rate < 30:
            status, status_label = "low_response", "کم‌پاسخ"
        elif reviews["total"] >= 3 and rating >= 4.5 and response_rate >= 70:
            status, status_label = "top", "عملکرد عالی"
        else:
            status, status_label = "normal", "متعادل"

        rows.append(
            {
                "id": str(business.id),
                "slug": business.slug,
                "name": business.name,
                "category": category_payload(business.category),
                "subcategory": subcategory_payload(business.subcategory),
                "view_count": int(business.view_count or 0),
                "quotes_suggested": offers["suggested"],
                "quotes_accepted": offers["accepted"],
                "response_rate": response_rate,
                "rating_avg": rating,
                "rating_count": int(business.rating_count or 0),
                "negative_rate": negative_rate,
                "status": status,
                "status_label": status_label,
            }
        )
    return {"items": rows}


async def map_data(session: AsyncSession) -> dict:
    business_rows = (
        await session.execute(
            sa.select(
                Business.id,
                Business.name,
                Business.slug,
                Business.geo_lat,
                Business.geo_lng,
                Category.name,
                Category.icon,
            )
            .join(Category, Business.category_id == Category.id)
            .where(
                Business.deleted_at.is_(None),
                Business.status == BusinessStatus.APPROVED,
                Business.geo_lat.is_not(None),
                Business.geo_lng.is_not(None),
            )
            .order_by(Business.name)
        )
    ).all()
    quote_rows = (
        await session.execute(
            sa.select(
                QuoteRequest.id,
                QuoteRequest.title,
                QuoteRequest.geo_lat,
                QuoteRequest.geo_lng,
                QuoteRequest.is_urgent,
                QuoteRequest.created_at,
                QuoteRequest.expires_at,
                Category.name,
            )
            .join(Category, QuoteRequest.category_id == Category.id)
            .where(
                QuoteRequest.deleted_at.is_(None),
                QuoteRequest.status == "active",
                QuoteRequest.geo_lat.is_not(None),
                QuoteRequest.geo_lng.is_not(None),
            )
            .order_by(QuoteRequest.created_at.desc())
        )
    ).all()
    businesses = [
        {
            "id": str(row[0]),
            "name": row[1],
            "slug": row[2],
            "lat": row[3],
            "lng": row[4],
            "category_name": row[5],
            "category_icon": row[6],
        }
        for row in business_rows
    ]
    quotes = []
    urgent_quotes = []
    for row in quote_rows:
        item = {
            "id": str(row[0]),
            "title": row[1],
            "lat": row[2],
            "lng": row[3],
            "is_urgent": bool(row[4]),
            "created_at": row[5].isoformat() if row[5] else None,
            "expires_at": as_utc(row[6]).isoformat() if row[6] else None,
            "category_name": row[7],
        }
        (urgent_quotes if item["is_urgent"] else quotes).append(item)
    return {
        "businesses": businesses,
        "quotes": quotes,
        "urgent_quotes": urgent_quotes,
    }


def _activity_union():
    user_name = sa.func.coalesce(User.full_name, User.phone, sa.literal("کاربر مهمان"))
    search = (
        sa.select(
            sa.literal("search").label("type"),
            sa.cast(SearchLog.id, sa.String).label("event_id"),
            SearchLog.created_at.label("occurred_at"),
            sa.cast(User.id, sa.String).label("user_id"),
            user_name.label("user_name"),
            sa.literal("جستجو").label("title"),
            sa.func.coalesce(SearchLog.query, sa.literal("بدون عبارت")).label("detail"),
            sa.literal("search").label("entity_type"),
            sa.cast(SearchLog.id, sa.String).label("entity_id"),
        )
        .select_from(SearchLog)
        .outerjoin(User, User.id == SearchLog.user_id)
    )
    user_registered = (
        sa.select(
            sa.literal("user_registered").label("type"),
            sa.cast(User.id, sa.String).label("event_id"),
            User.created_at.label("occurred_at"),
            sa.cast(User.id, sa.String).label("user_id"),
            user_name.label("user_name"),
            sa.literal("ثبت‌نام کاربر").label("title"),
            sa.func.coalesce(User.full_name, User.phone).label("detail"),
            sa.literal("user").label("entity_type"),
            sa.cast(User.id, sa.String).label("entity_id"),
        )
        .select_from(User)
        .where(User.deleted_at.is_(None))
    )
    business_created = (
        sa.select(
            sa.literal("business_created").label("type"),
            sa.cast(Business.id, sa.String).label("event_id"),
            Business.created_at.label("occurred_at"),
            sa.cast(User.id, sa.String).label("user_id"),
            user_name.label("user_name"),
            sa.literal("ثبت کسب‌وکار").label("title"),
            Business.name.label("detail"),
            sa.literal("business").label("entity_type"),
            sa.cast(Business.id, sa.String).label("entity_id"),
        )
        .select_from(Business)
        .join(User, User.id == Business.owner_id)
        .where(Business.deleted_at.is_(None))
    )
    review_created = (
        sa.select(
            sa.literal("review_created").label("type"),
            sa.cast(Review.id, sa.String).label("event_id"),
            Review.created_at.label("occurred_at"),
            sa.cast(User.id, sa.String).label("user_id"),
            user_name.label("user_name"),
            sa.literal("ثبت نظر").label("title"),
            Business.name.label("detail"),
            sa.literal("business").label("entity_type"),
            sa.cast(Business.id, sa.String).label("entity_id"),
        )
        .select_from(Review)
        .join(User, User.id == Review.user_id)
        .join(Business, Business.id == Review.business_id)
        .where(Review.deleted_at.is_(None))
    )
    quote_requested = (
        sa.select(
            sa.literal("quote_requested").label("type"),
            sa.cast(QuoteRequest.id, sa.String).label("event_id"),
            QuoteRequest.created_at.label("occurred_at"),
            sa.cast(User.id, sa.String).label("user_id"),
            user_name.label("user_name"),
            sa.literal("درخواست قیمت").label("title"),
            QuoteRequest.title.label("detail"),
            sa.literal("quote").label("entity_type"),
            sa.cast(QuoteRequest.id, sa.String).label("entity_id"),
        )
        .select_from(QuoteRequest)
        .join(User, User.id == QuoteRequest.customer_id)
        .where(QuoteRequest.deleted_at.is_(None))
    )
    quote_offer = (
        sa.select(
            sa.literal("quote_offer").label("type"),
            sa.cast(Offer.id, sa.String).label("event_id"),
            Offer.created_at.label("occurred_at"),
            sa.cast(User.id, sa.String).label("user_id"),
            user_name.label("user_name"),
            sa.literal("ارسال پیشنهاد قیمت").label("title"),
            Business.name.label("detail"),
            sa.literal("quote").label("entity_type"),
            sa.cast(QuoteRequest.id, sa.String).label("entity_id"),
        )
        .select_from(Offer)
        .join(Business, Business.id == Offer.business_id)
        .join(QuoteRequest, QuoteRequest.id == Offer.request_id)
        .join(User, User.id == Business.owner_id)
        .where(Offer.deleted_at.is_(None))
    )
    quote_seen = (
        sa.select(
            sa.literal("quote_seen").label("type"),
            sa.cast(QuoteDelivery.id, sa.String).label("event_id"),
            QuoteDelivery.seen_at.label("occurred_at"),
            sa.cast(User.id, sa.String).label("user_id"),
            user_name.label("user_name"),
            sa.literal("مشاهده درخواست").label("title"),
            Business.name.label("detail"),
            sa.literal("quote").label("entity_type"),
            sa.cast(QuoteRequest.id, sa.String).label("entity_id"),
        )
        .select_from(QuoteDelivery)
        .join(Business, Business.id == QuoteDelivery.business_id)
        .join(QuoteRequest, QuoteRequest.id == QuoteDelivery.request_id)
        .join(User, User.id == Business.owner_id)
        .where(QuoteDelivery.seen_at.is_not(None))
    )
    quote_chosen = (
        sa.select(
            sa.literal("quote_chosen").label("type"),
            sa.cast(QuoteRequest.id, sa.String).label("event_id"),
            QuoteRequest.accepted_at.label("occurred_at"),
            sa.cast(User.id, sa.String).label("user_id"),
            user_name.label("user_name"),
            sa.literal("انتخاب پیشنهاد").label("title"),
            QuoteRequest.title.label("detail"),
            sa.literal("quote").label("entity_type"),
            sa.cast(QuoteRequest.id, sa.String).label("entity_id"),
        )
        .select_from(QuoteRequest)
        .join(User, User.id == QuoteRequest.customer_id)
        .where(
            QuoteRequest.deleted_at.is_(None),
            QuoteRequest.accepted_at.is_not(None),
        )
    )
    return sa.union_all(
        search,
        user_registered,
        business_created,
        review_created,
        quote_requested,
        quote_offer,
        quote_seen,
        quote_chosen,
    ).subquery("activity_events")


async def activity_logs(
    session: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 25,
    event_type: str | None = None,
) -> dict:
    if event_type and event_type not in EVENT_TYPES:
        from app.core.errors import AppError

        raise AppError("validation_error", "invalid_event_type", 422)
    events = _activity_union()
    filters = [events.c.type == event_type] if event_type else []
    total = await _count(
        session, sa.select(sa.func.count()).select_from(events).where(*filters)
    )
    page = max(1, page)
    per_page = min(100, max(1, per_page))
    rows = (
        await session.execute(
            sa.select(events)
            .where(*filters)
            .order_by(events.c.occurred_at.desc(), events.c.type)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    return {
        "items": [
            {
                "id": f"{row.type}:{row.event_id}",
                "type": row.type,
                "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
                "user_id": row.user_id,
                "user_name": row.user_name or "کاربر مهمان",
                "title": row.title,
                "detail": row.detail,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
            }
            for row in rows
        ],
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": max(1, (total + per_page - 1) // per_page),
        },
    }


async def activity_log_summary(session: AsyncSession, *, days: int = 14) -> dict:
    days = min(30, max(7, days))
    events = _activity_union()
    by_type = (
        await session.execute(
            sa.select(events.c.type, sa.func.count())
            .group_by(events.c.type)
            .order_by(sa.func.count().desc())
        )
    ).all()

    today = today_local()
    start = start_of_day_utc(today - timedelta(days=days - 1))
    rows = (
        await session.execute(
            sa.select(events.c.type, events.c.occurred_at).where(
                events.c.occurred_at >= start
            )
        )
    ).all()
    counts: dict[date, Counter] = {}
    for event_type, occurred_at in rows:
        if occurred_at is None:
            continue
        day = local_date(occurred_at)
        counts.setdefault(day, Counter())[event_type] += 1
    daily = []
    for offset in range(days):
        day = today - timedelta(days=days - 1 - offset)
        day_counts = counts.get(day, Counter())
        daily.append(
            {
                "date": day.isoformat(),
                "total": sum(day_counts.values()),
            }
        )
    return {
        "by_type": [
            {"type": event_type, "count": int(count)}
            for event_type, count in by_type
        ],
        "daily": daily,
        "total": sum(int(count) for _, count in by_type),
    }
