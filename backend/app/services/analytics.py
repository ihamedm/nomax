"""Admin analytics aggregation.

All timestamps are generated in UTC and grouped in the Tehran timezone. Queries
stay portable between PostgreSQL and the SQLite test database by fetching
timestamp rows and doing the day/hour bucketing in Python; the row counts here
are small (dashboard ranges), while heavy grouping happens in SQL.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import QuoteDelivery, SearchLog
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.quote import Offer, QuoteRequest
from app.models.review import Review
from app.models.user import User

TEHRAN = ZoneInfo("Asia/Tehran")
UTC = timezone.utc

QUOTE_STATUSES = ("active", "accepted", "cancelled", "expired")
ROLE_LABELS = {
    "customer": "مشتری",
    "owner": "کسب‌وکار",
    "admin": "مدیر",
    "superadmin": "مدیر کل",
}


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def local_date(value: datetime) -> date:
    return as_utc(value).astimezone(TEHRAN).date()  # type: ignore[union-attr]


def local_hour(value: datetime) -> int:
    return as_utc(value).astimezone(TEHRAN).hour  # type: ignore[union-attr]


def start_of_day_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=TEHRAN).astimezone(UTC)


def today_local() -> date:
    return datetime.now(UTC).astimezone(TEHRAN).date()


def start_of_week_utc(day: date) -> datetime:
    # Iranian week starts on Saturday (Python weekday: Saturday == 5).
    saturday = day - timedelta(days=(day.weekday() - 5) % 7)
    return start_of_day_utc(saturday)


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def rate(part: int, total: int) -> float:
    return round((part / total) * 100, 1) if total else 0


async def _scalar(session: AsyncSession, stmt) -> int:
    return int((await session.execute(stmt)).scalar() or 0)


async def _daily_counts(
    session: AsyncSession,
    model,
    start: datetime,
    column=None,
    *extra_conditions,
) -> Counter:
    column = column or model.created_at
    rows = (
        await session.execute(
            sa.select(column).where(column >= start, *extra_conditions)
        )
    ).scalars().all()
    return Counter(local_date(row) for row in rows if row is not None)


async def overview(session: AsyncSession, *, days: int = 14) -> dict:
    days = min(30, max(7, days))
    today = today_local()
    start = start_of_day_utc(today - timedelta(days=days - 1))
    today_start = start_of_day_utc(today)

    search_days = await _daily_counts(session, SearchLog, start)
    quote_days = await _daily_counts(
        session, QuoteRequest, start, QuoteRequest.created_at, QuoteRequest.deleted_at.is_(None)
    )
    offer_days = await _daily_counts(
        session,
        Offer,
        start,
        Offer.created_at,
        Offer.deleted_at.is_(None),
        Offer.status != "declined",
    )
    registration_days = await _daily_counts(
        session, User, start, User.created_at, User.deleted_at.is_(None)
    )

    daily = []
    for offset in range(days):
        day = today - timedelta(days=days - 1 - offset)
        daily.append(
            {
                "date": day.isoformat(),
                "searches": search_days.get(day, 0),
                "quote_requests": quote_days.get(day, 0),
                "quote_responses": offer_days.get(day, 0),
                "registrations": registration_days.get(day, 0),
            }
        )

    search_hours = [
        local_hour(row)
        for row in (
            await session.execute(
                sa.select(SearchLog.created_at).where(SearchLog.created_at >= today_start)
            )
        ).scalars().all()
        if row is not None
    ]
    quote_hours = [
        local_hour(row)
        for row in (
            await session.execute(
                sa.select(QuoteRequest.created_at).where(
                    QuoteRequest.created_at >= today_start,
                    QuoteRequest.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        if row is not None
    ]
    search_hour_counts = Counter(search_hours)
    quote_hour_counts = Counter(quote_hours)
    hourly = [
        {
            "hour": hour,
            "searches": search_hour_counts.get(hour, 0),
            "quote_requests": quote_hour_counts.get(hour, 0),
        }
        for hour in range(24)
    ]

    roles = (
        await session.execute(
            sa.select(User.role, sa.func.count(User.id))
            .where(User.deleted_at.is_(None))
            .group_by(User.role)
        )
    ).all()
    role_counts = Counter()
    for role, count in roles:
        role_counts[role.value if hasattr(role, "value") else str(role)] += int(count)
    role_items = [
        {
            "role": role,
            "label": ROLE_LABELS.get(role, role),
            "count": role_counts.get(role, 0),
        }
        for role in ("customer", "owner", "admin", "superadmin")
    ]

    businesses_total = await _scalar(
        session, sa.select(sa.func.count(Business.id)).where(Business.deleted_at.is_(None))
    )
    businesses_approved = await _scalar(
        session,
        sa.select(sa.func.count(Business.id)).where(
            Business.deleted_at.is_(None), Business.status == BusinessStatus.APPROVED
        ),
    )
    reviews_total = await _scalar(
        session, sa.select(sa.func.count(Review.id)).where(Review.deleted_at.is_(None))
    )
    quotes_total = await _scalar(
        session,
        sa.select(sa.func.count(QuoteRequest.id)).where(QuoteRequest.deleted_at.is_(None)),
    )
    searches_total = await _scalar(session, sa.select(sa.func.count(SearchLog.id)))
    users_total = await _scalar(
        session, sa.select(sa.func.count(User.id)).where(User.deleted_at.is_(None))
    )
    pending_businesses = await _scalar(
        session,
        sa.select(sa.func.count(Business.id)).where(
            Business.deleted_at.is_(None), Business.status == BusinessStatus.PENDING
        ),
    )
    pending_reviews = await _scalar(
        session,
        sa.select(sa.func.count(Review.id)).where(
            Review.deleted_at.is_(None),
            Review.is_private.is_(False),
            Review.status == "pending",
        ),
    )
    answered_requests = sa.select(Offer.request_id).where(
        Offer.deleted_at.is_(None), Offer.status != "declined"
    )
    quotes_without_offers = await _scalar(
        session,
        sa.select(sa.func.count(QuoteRequest.id)).where(
            QuoteRequest.deleted_at.is_(None),
            QuoteRequest.status == "active",
            QuoteRequest.id.not_in(answered_requests),
        ),
    )

    async def funnel_range(start_at: datetime | None) -> dict:
        request_where = [QuoteRequest.deleted_at.is_(None)]
        delivery_sent_where = []
        delivery_seen_where = [QuoteDelivery.seen_at.is_not(None)]
        offer_where = [Offer.deleted_at.is_(None), Offer.status != "declined"]
        chosen_where = [QuoteRequest.deleted_at.is_(None), QuoteRequest.accepted_at.is_not(None)]
        if start_at is not None:
            request_where.append(QuoteRequest.created_at >= start_at)
            delivery_sent_where.append(QuoteDelivery.sent_at >= start_at)
            delivery_seen_where.append(QuoteDelivery.seen_at >= start_at)
            offer_where.append(Offer.created_at >= start_at)
            chosen_where.append(QuoteRequest.accepted_at >= start_at)

        requests = await _scalar(
            session, sa.select(sa.func.count(QuoteRequest.id)).where(*request_where)
        )
        sent = await _scalar(
            session,
            sa.select(sa.func.count(sa.func.distinct(QuoteDelivery.request_id))).where(
                *delivery_sent_where
            ),
        )
        seen = await _scalar(
            session,
            sa.select(sa.func.count(sa.func.distinct(QuoteDelivery.request_id))).where(
                *delivery_seen_where
            ),
        )
        responded = await _scalar(
            session,
            sa.select(sa.func.count(sa.func.distinct(Offer.request_id))).where(*offer_where),
        )
        chosen = await _scalar(
            session, sa.select(sa.func.count(QuoteRequest.id)).where(*chosen_where)
        )
        return {
            "requests": requests,
            "sent": sent,
            "seen": seen,
            "responded": responded,
            "chosen": chosen,
        }

    week_start = start_of_week_utc(today)
    month_start = start_of_day_utc(today.replace(day=1))
    quote_funnel = [
        {"range": "today", "counts": await funnel_range(today_start)},
        {"range": "week", "counts": await funnel_range(week_start)},
        {"range": "month", "counts": await funnel_range(month_start)},
        {"range": "all", "counts": await funnel_range(None)},
    ]

    return {
        "widgets": {
            "businesses_total": businesses_total,
            "businesses_approved": businesses_approved,
            "reviews_total": reviews_total,
            "quotes_total": quotes_total,
            "searches_total": searches_total,
            "users_total": users_total,
        },
        "pending": {
            "businesses": pending_businesses,
            "reviews": pending_reviews,
            "quotes": quotes_without_offers,
            "total": pending_businesses + pending_reviews + quotes_without_offers,
        },
        "daily": daily,
        "hourly": hourly,
        "roles": role_items,
        "quote_funnel": quote_funnel,
    }


async def quote_analytics(session: AsyncSession) -> dict:
    quotes = (
        await session.execute(
            sa.select(
                QuoteRequest.id,
                QuoteRequest.created_at,
                QuoteRequest.accepted_at,
                QuoteRequest.status,
            ).where(QuoteRequest.deleted_at.is_(None))
        )
    ).all()
    quote_rows = {row.id: row for row in quotes}

    status_counts = Counter(
        row.status.value if hasattr(row.status, "value") else str(row.status)
        for row in quotes
    )
    statuses = [
        {"status": status, "count": status_counts.get(status, 0)}
        for status in QUOTE_STATUSES
    ]

    offers = (
        await session.execute(
            sa.select(Offer.request_id, Offer.created_at, Offer.status).where(
                Offer.deleted_at.is_(None)
            )
        )
    ).all()
    accepted_offers = sum(
        1 for row in offers if (row.status.value if hasattr(row.status, "value") else row.status) == "accepted"
    )
    pending_offers = sum(
        1 for row in offers if (row.status.value if hasattr(row.status, "value") else row.status) == "pending"
    )

    first_offer = {}
    for request_id, created_at, status in offers:
        normalized = status.value if hasattr(status, "value") else str(status)
        if normalized == "declined" or created_at is None:
            continue
        current = first_offer.get(request_id)
        if current is None or created_at < current:
            first_offer[request_id] = created_at

    first_seen_rows = (
        await session.execute(
            sa.select(
                QuoteDelivery.request_id,
                sa.func.min(QuoteDelivery.seen_at),
            )
            .where(QuoteDelivery.seen_at.is_not(None))
            .group_by(QuoteDelivery.request_id)
        )
    ).all()
    first_seen = {
        request_id: seen_at for request_id, seen_at in first_seen_rows if seen_at is not None
    }

    first_sent_rows = (
        await session.execute(
            sa.select(
                QuoteDelivery.request_id,
                sa.func.min(QuoteDelivery.sent_at),
            ).group_by(QuoteDelivery.request_id)
        )
    ).all()
    first_sent = {
        request_id: sent_at for request_id, sent_at in first_sent_rows if sent_at is not None
    }

    def seconds_between(start, end) -> float | None:
        start, end = as_utc(start), as_utc(end)
        if start is None or end is None:
            return None
        seconds = (end - start).total_seconds()
        return seconds if seconds >= 0 else None

    timings = {
        "sent": [],
        "seen": [],
        "offer": [],
        "choice": [],
    }
    chosen_quotes = 0
    for row in quotes:
        if row.accepted_at is not None:
            chosen_quotes += 1
        sent_at = first_sent.get(row.id)
        seen_at = first_seen.get(row.id)
        offer_at = first_offer.get(row.id)
        for key, end in (
            ("sent", sent_at),
            ("seen", seen_at),
            ("offer", offer_at),
            ("choice", row.accepted_at),
        ):
            value = seconds_between(row.created_at, end)
            if value is not None:
                timings[key].append(value)

    timing_items = [
        {
            "key": key,
            "avg_seconds": average(values),
            "count": len(values),
        }
        for key, values in timings.items()
    ]

    total = len(quotes)
    seen_requests = len(first_seen)
    responded_requests = len(first_offer)
    return {
        "widgets": {
            "total": total,
            "active": status_counts.get("active", 0),
            "accepted": status_counts.get("accepted", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "expired": status_counts.get("expired", 0),
            "offers_total": len(offers),
            "accepted_offers": accepted_offers,
            "pending_offers": pending_offers,
            "seen_requests": seen_requests,
            "responded_requests": responded_requests,
            "chosen_quotes": chosen_quotes,
            "seen_rate": rate(seen_requests, total),
            "response_rate": rate(responded_requests, total),
            "choice_rate": rate(status_counts.get("accepted", 0), total),
            "avg_offer_seconds": average(timings["offer"]),
            "avg_choice_seconds": average(timings["choice"]),
        },
        "statuses": statuses,
        "timings": timing_items,
    }


def _market_status(
    *, businesses: int, demand: int, quotes: int, unanswered: int, no_results: int
) -> tuple[str, str]:
    if demand == 0 and businesses == 0:
        return "empty", "بدون داده"
    if businesses == 0:
        return "no_supply", "بدون عرضه"
    if demand == 0:
        return "no_demand", "بدون تقاضا"
    if unanswered >= 3 and unanswered / max(quotes, 1) >= 0.5:
        return "urgent", "جذب فوری"
    if no_results >= 3 or demand / businesses >= 4:
        return "shortage", "کمبود عرضه"
    if businesses >= demand * 2:
        return "surplus", "عرضه مازاد"
    return "balanced", "متعادل"


async def market_analytics(session: AsyncSession) -> dict:
    categories = (
        await session.execute(
            sa.select(Category.id, Category.name, Category.icon, Category.slug)
            .where(Category.deleted_at.is_(None), Category.is_active.is_(True))
            .order_by(Category.sort_order, Category.id)
        )
    ).all()

    business_counts = dict(
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
    search_counts = dict(
        (
            await session.execute(
                sa.select(SearchLog.category_id, sa.func.count(SearchLog.id))
                .where(SearchLog.category_id.is_not(None))
                .group_by(SearchLog.category_id)
            )
        ).all()
    )
    no_result_counts = dict(
        (
            await session.execute(
                sa.select(SearchLog.category_id, sa.func.count(SearchLog.id))
                .where(
                    SearchLog.category_id.is_not(None),
                    SearchLog.results_count == 0,
                )
                .group_by(SearchLog.category_id)
            )
        ).all()
    )
    quote_counts = dict(
        (
            await session.execute(
                sa.select(QuoteRequest.category_id, sa.func.count(QuoteRequest.id))
                .where(QuoteRequest.deleted_at.is_(None))
                .group_by(QuoteRequest.category_id)
            )
        ).all()
    )
    answered_requests = sa.select(Offer.request_id).where(
        Offer.deleted_at.is_(None), Offer.status != "declined"
    )
    unanswered_counts = dict(
        (
            await session.execute(
                sa.select(QuoteRequest.category_id, sa.func.count(QuoteRequest.id))
                .where(
                    QuoteRequest.deleted_at.is_(None),
                    QuoteRequest.status == "active",
                    QuoteRequest.id.not_in(answered_requests),
                )
                .group_by(QuoteRequest.category_id)
            )
        ).all()
    )

    category_rows = []
    for category_id, name, icon, slug in categories:
        businesses = int(business_counts.get(category_id, 0))
        searches = int(search_counts.get(category_id, 0))
        quotes = int(quote_counts.get(category_id, 0))
        no_results = int(no_result_counts.get(category_id, 0))
        unanswered = int(unanswered_counts.get(category_id, 0))
        demand = searches + quotes
        status_key, status_label = _market_status(
            businesses=businesses,
            demand=demand,
            quotes=quotes,
            unanswered=unanswered,
            no_results=no_results,
        )
        category_rows.append(
            {
                "id": category_id,
                "name": name,
                "icon": icon,
                "slug": slug,
                "businesses": businesses,
                "searches": searches,
                "no_results": no_results,
                "quotes": quotes,
                "unanswered_quotes": unanswered,
                "demand": demand,
                "status": status_key,
                "status_label": status_label,
            }
        )
    category_rows.sort(key=lambda row: (-row["demand"], -row["businesses"], row["name"]))

    subcategories = (
        await session.execute(
            sa.select(
                Subcategory.id,
                Subcategory.name,
                Subcategory.category_id,
            ).where(Subcategory.deleted_at.is_(None))
        )
    ).all()
    sub_business_counts = dict(
        (
            await session.execute(
                sa.select(Business.subcategory_id, sa.func.count(Business.id))
                .where(
                    Business.deleted_at.is_(None),
                    Business.status == BusinessStatus.APPROVED,
                    Business.subcategory_id.is_not(None),
                )
                .group_by(Business.subcategory_id)
            )
        ).all()
    )
    sub_search_counts = dict(
        (
            await session.execute(
                sa.select(SearchLog.subcategory_id, sa.func.count(SearchLog.id))
                .where(SearchLog.subcategory_id.is_not(None))
                .group_by(SearchLog.subcategory_id)
            )
        ).all()
    )
    sub_quote_counts = dict(
        (
            await session.execute(
                sa.select(QuoteRequest.subcategory_id, sa.func.count(QuoteRequest.id))
                .where(
                    QuoteRequest.deleted_at.is_(None),
                    QuoteRequest.subcategory_id.is_not(None),
                )
                .group_by(QuoteRequest.subcategory_id)
            )
        ).all()
    )
    category_names = {category_id: name for category_id, name, _, _ in categories}
    subcategory_rows = []
    for sub_id, name, category_id in subcategories:
        searches = int(sub_search_counts.get(sub_id, 0))
        quotes = int(sub_quote_counts.get(sub_id, 0))
        subcategory_rows.append(
            {
                "id": sub_id,
                "name": name,
                "category_name": category_names.get(category_id, ""),
                "searches": searches,
                "quotes": quotes,
                "businesses": int(sub_business_counts.get(sub_id, 0)),
                "demand": searches + quotes,
            }
        )
    subcategory_rows.sort(key=lambda row: (-row["demand"], -row["businesses"], row["name"]))
    subcategory_rows = [row for row in subcategory_rows if row["demand"] > 0][:15]

    keyword_rows = (
        await session.execute(
            sa.select(
                SearchLog.normalized_query,
                sa.func.count(SearchLog.id),
                sa.func.avg(SearchLog.results_count),
                sa.func.sum(
                    sa.case((SearchLog.results_count == 0, 1), else_=0)
                ),
            )
            .where(SearchLog.normalized_query.is_not(None))
            .group_by(SearchLog.normalized_query)
            .order_by(sa.func.count(SearchLog.id).desc())
            .limit(15)
        )
    ).all()
    keywords = [
        {
            "keyword": keyword,
            "searches": int(count),
            "avg_results": round(float(avg_results or 0), 1),
            "no_results": int(no_results or 0),
        }
        for keyword, count, avg_results, no_results in keyword_rows
    ]

    no_result_rows = (
        await session.execute(
            sa.select(
                SearchLog.normalized_query,
                SearchLog.category_id,
                sa.func.count(SearchLog.id),
            )
            .where(
                SearchLog.normalized_query.is_not(None),
                SearchLog.results_count == 0,
            )
            .group_by(SearchLog.normalized_query, SearchLog.category_id)
            .order_by(sa.func.count(SearchLog.id).desc())
            .limit(15)
        )
    ).all()
    no_result_keywords = [
        {
            "keyword": keyword,
            "searches": int(count),
            "category_id": category_id,
            "category_name": category_names.get(category_id, "نامشخص"),
        }
        for keyword, category_id, count in no_result_rows
    ]

    return {
        "categories": category_rows,
        "subcategories": subcategory_rows,
        "keywords": keywords,
        "no_result_keywords": no_result_keywords,
    }
