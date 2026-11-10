"""Aggregations for the admin home dashboard.

The dashboard is a read-only summary: headline counts, a short growth trend,
pending queues and the latest activity. Everything is computed with a handful
of grouped queries so the page loads in one request; the heavier per-category
market analysis stays in `app.services.analytics`.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import SearchLog
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.quote import Offer, QuoteRequest
from app.models.review import Review
from app.models.user import User
from app.services import analytics as analytics_service
from app.services import analytics_extra

BUSINESS_STATUS_LABELS = {
    "pending": "در انتظار تأیید",
    "approved": "تأییدشده",
    "rejected": "ردشده",
}
BUSINESS_STATUS_COLORS = {
    "pending": "#f59e0b",
    "approved": "#10b981",
    "rejected": "#f43f5e",
}

MIN_DAYS = 7
MAX_DAYS = 30


def _pct_change(current: int, previous: int) -> float | None:
    """Percent change, or ``None`` when there is no baseline to compare with."""
    if previous <= 0:
        return None if current <= 0 else 100.0
    return round(((current - previous) / previous) * 100, 1)


async def _count(session: AsyncSession, stmt) -> int:
    return int((await session.execute(stmt)).scalar() or 0)


async def _grouped_counts(session: AsyncSession, column, *conditions) -> Counter:
    rows = (await session.execute(sa.select(column).where(*conditions))).scalars().all()
    counter: Counter = Counter()
    for row in rows:
        counter[row.value if hasattr(row, "value") else row] += 1
    return counter


async def _daily_counts(session: AsyncSession, model, start: datetime, *conditions) -> Counter:
    rows = (
        await session.execute(
            sa.select(model.created_at).where(model.created_at >= start, *conditions)
        )
    ).scalars().all()
    return Counter(
        analytics_service.local_date(row) for row in rows if row is not None
    )


async def overview(
    session: AsyncSession,
    *,
    days: int = 14,
    can_stats: bool = True,
    can_business: bool = False,
    can_review: bool = False,
    can_quote: bool = False,
) -> dict:
    days = min(MAX_DAYS, max(MIN_DAYS, days))
    now = datetime.now(timezone.utc)
    today = analytics_service.today_local()
    start = analytics_service.start_of_day_utc(today - timedelta(days=days - 1))
    window_start = analytics_service.start_of_day_utc(today - timedelta(days=6))
    previous_start = analytics_service.start_of_day_utc(today - timedelta(days=13))

    # Pending queues are cheap and useful even without `stats.read`.
    pending_businesses = await _count(
        session,
        sa.select(sa.func.count(Business.id)).where(
            Business.deleted_at.is_(None), Business.status == BusinessStatus.PENDING
        ),
    )
    pending_reviews = await _count(
        session,
        sa.select(sa.func.count(Review.id)).where(
            Review.deleted_at.is_(None),
            Review.is_private.is_(False),
            Review.status == "pending",
        ),
    )
    answered = sa.select(Offer.request_id).where(
        Offer.deleted_at.is_(None), Offer.status != "declined"
    )
    unanswered_quotes = await _count(
        session,
        sa.select(sa.func.count(QuoteRequest.id)).where(
            QuoteRequest.deleted_at.is_(None),
            QuoteRequest.status == "active",
            QuoteRequest.id.not_in(answered),
        ),
    )

    queues: list[dict] = []
    if can_business:
        queues.append(
            {
                "key": "businesses",
                "label": "کسب‌وکار در انتظار تأیید",
                "count": pending_businesses,
                "to": "/admin/businesses?status=pending",
                "tone": "amber",
            }
        )
    if can_review:
        queues.append(
            {
                "key": "reviews",
                "label": "نظر در انتظار بررسی",
                "count": pending_reviews,
                "to": "/admin/reviews?status=pending",
                "tone": "rose",
            }
        )
    if can_quote:
        queues.append(
            {
                "key": "quotes",
                "label": "استعلام بدون پاسخ",
                "count": unanswered_quotes,
                "to": "/admin/quotes?status=active",
                "tone": "brand",
            }
        )

    activity = await analytics_extra.activity_logs(session, page=1, per_page=9)

    payload: dict = {
        "generated_at": now.isoformat(),
        "days": days,
        "queues": queues,
        "recent_activity": activity["items"],
        "stats": None,
    }
    if not can_stats:
        return payload

    # --- headline counts -------------------------------------------------
    business_status = await _grouped_counts(
        session,
        Business.status,
        Business.deleted_at.is_(None),
    )
    role_counts = await _grouped_counts(
        session,
        User.role,
        User.deleted_at.is_(None),
    )
    users_total = sum(role_counts.values())
    users_verified = await _count(
        session,
        sa.select(sa.func.count(User.id)).where(
            User.deleted_at.is_(None), User.is_verified.is_(True)
        ),
    )

    reviews_total = await _count(
        session,
        sa.select(sa.func.count(Review.id)).where(Review.deleted_at.is_(None)),
    )
    rating_avg = float(
        (
            await session.execute(
                sa.select(sa.func.avg(Business.rating_avg)).where(
                    Business.deleted_at.is_(None),
                    Business.status == BusinessStatus.APPROVED,
                    Business.rating_count > 0,
                )
            )
        ).scalar()
        or 0
    )

    quote_status = await _grouped_counts(
        session,
        QuoteRequest.status,
        QuoteRequest.deleted_at.is_(None),
    )
    quotes_total = sum(quote_status.values())

    searches_total = await _count(session, sa.select(sa.func.count(SearchLog.id)))

    # --- rolling seven-day deltas ---------------------------------------
    async def window_count(model, *conditions) -> tuple[int, int]:
        current = await _count(
            session,
            sa.select(sa.func.count()).select_from(model).where(
                model.created_at >= window_start, *conditions
            ),
        )
        previous = await _count(
            session,
            sa.select(sa.func.count()).select_from(model).where(
                model.created_at >= previous_start,
                model.created_at < window_start,
                *conditions,
            ),
        )
        return current, previous

    users_7d, users_prev = await window_count(User, User.deleted_at.is_(None))
    businesses_7d, businesses_prev = await window_count(
        Business, Business.deleted_at.is_(None)
    )
    reviews_7d, reviews_prev = await window_count(Review, Review.deleted_at.is_(None))
    quotes_7d, quotes_prev = await window_count(
        QuoteRequest, QuoteRequest.deleted_at.is_(None)
    )
    searches_7d, searches_prev = await window_count(SearchLog)
    no_result_7d = await _count(
        session,
        sa.select(sa.func.count(SearchLog.id)).where(
            SearchLog.created_at >= window_start, SearchLog.results_count == 0
        ),
    )

    # --- daily trend -----------------------------------------------------
    user_days = await _daily_counts(session, User, start, User.deleted_at.is_(None))
    business_days = await _daily_counts(
        session, Business, start, Business.deleted_at.is_(None)
    )
    review_days = await _daily_counts(session, Review, start, Review.deleted_at.is_(None))
    quote_days = await _daily_counts(
        session, QuoteRequest, start, QuoteRequest.deleted_at.is_(None)
    )
    search_days = await _daily_counts(session, SearchLog, start)

    trend = []
    for offset in range(days):
        day = today - timedelta(days=days - 1 - offset)
        trend.append(
            {
                "date": day.isoformat(),
                "users": user_days.get(day, 0),
                "businesses": business_days.get(day, 0),
                "reviews": review_days.get(day, 0),
                "quotes": quote_days.get(day, 0),
                "searches": search_days.get(day, 0),
            }
        )

    # --- category supply vs demand --------------------------------------
    categories = (
        await session.execute(
            sa.select(Category.id, Category.name, Category.icon)
            .where(Category.deleted_at.is_(None), Category.is_active.is_(True))
            .order_by(Category.sort_order, Category.id)
        )
    ).all()
    category_businesses = dict(
        (
            await session.execute(
                sa.select(Business.category_id, sa.func.count(Business.id))
                .where(
                    Business.deleted_at.is_(None),
                    Business.status == BusinessStatus.APPROVED,
                )
                .group_by(Business.category_id)
            )
        ).all()
    )
    category_searches = dict(
        (
            await session.execute(
                sa.select(SearchLog.category_id, sa.func.count(SearchLog.id))
                .where(SearchLog.category_id.is_not(None))
                .group_by(SearchLog.category_id)
            )
        ).all()
    )
    top_categories = sorted(
        (
            {
                "id": category_id,
                "name": name,
                "icon": icon or "",
                "businesses": int(category_businesses.get(category_id, 0)),
                "searches": int(category_searches.get(category_id, 0)),
            }
            for category_id, name, icon in categories
        ),
        key=lambda item: (item["businesses"] + item["searches"], item["name"]),
        reverse=True,
    )[:6]

    payload["stats"] = {
        "businesses": {
            "total": sum(business_status.values()),
            "approved": business_status.get("approved", 0),
            "pending": business_status.get("pending", 0),
            "rejected": business_status.get("rejected", 0),
            "last_7d": businesses_7d,
            "change": _pct_change(businesses_7d, businesses_prev),
        },
        "users": {
            "total": users_total,
            "verified": users_verified,
            "verified_rate": round(users_verified / users_total * 100, 1) if users_total else 0.0,
            "last_7d": users_7d,
            "change": _pct_change(users_7d, users_prev),
        },
        "reviews": {
            "total": reviews_total,
            "pending": pending_reviews,
            "avg_rating": round(rating_avg, 2),
            "last_7d": reviews_7d,
            "change": _pct_change(reviews_7d, reviews_prev),
        },
        "quotes": {
            "total": quotes_total,
            "active": quote_status.get("active", 0),
            "unanswered": unanswered_quotes,
            "last_7d": quotes_7d,
            "change": _pct_change(quotes_7d, quotes_prev),
        },
        "searches": {
            "total": searches_total,
            "last_7d": searches_7d,
            "change": _pct_change(searches_7d, searches_prev),
            "no_result_7d": no_result_7d,
            "no_result_rate": round(no_result_7d / searches_7d * 100, 1) if searches_7d else 0.0,
        },
    }
    payload["trend"] = trend
    payload["business_status"] = [
        {
            "status": status,
            "label": BUSINESS_STATUS_LABELS[status],
            "color": BUSINESS_STATUS_COLORS[status],
            "count": business_status.get(status, 0),
        }
        for status in ("approved", "pending", "rejected")
    ]
    payload["roles"] = [
        {"role": role, "label": analytics_service.ROLE_LABELS.get(role, role), "count": count}
        for role, count in role_counts.most_common()
    ]
    payload["top_categories"] = top_categories
    return payload
