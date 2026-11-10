"""Multi-wave quote dispatch engine.

The previous implementation was a single UTC-based pass with an exact
subcategory filter. A request could therefore be created successfully yet reach
nobody: normal requests created outside the UTC window were dropped, and a
missing exact subcategory excluded every business in the parent category.

This engine is database-first and deterministic:

* candidate matching walks a ladder — exact subcategory inside the tight radius,
  category inside radius, expanded radius, then category-wide fallback;
* each wave targets a configurable batch and never repeats an owner;
* the request row stores the next retry time, so a lost Redis message can be
  reconciled by the worker;
* quiet hours are evaluated in Tehran, not UTC;
* manual admin assignment bypasses matching but is still recorded as a wave.

Businesses are never sent a request they already received, regardless of whether
the delivery was automatic or manual.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import QuoteDelivery, QuoteDispatchRun
from app.models.business import Business, BusinessStatus
from app.models.quote import Offer, QuoteRequest
from app.services.inapp_notifications import notify_quote_request
from app.services.quote_dispatch_settings import QuoteDispatchConfig, get_quote_dispatch_config

DISPATCH_RADIUS_KM = 10.0
TEHRAN = ZoneInfo("Asia/Tehran")
ACTIVE = "active"
COMPLETED = "completed"
EXPIRED = "expired"
CANCELLED = "cancelled"
ACCEPTED = "accepted"


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_daytime(now: datetime, config: QuoteDispatchConfig) -> bool:
    local_hour = now.astimezone(TEHRAN).hour
    return config.day_start_hour <= local_hour < config.day_end_hour


def next_day_window(now: datetime, config: QuoteDispatchConfig) -> datetime:
    """Return the next Tehran-local sending window start, as UTC."""
    local = now.astimezone(TEHRAN)
    start = local.replace(
        hour=config.day_start_hour, minute=0, second=0, microsecond=0
    )
    if local.hour < config.day_start_hour:
        return start.astimezone(timezone.utc)
    if local.hour >= config.day_end_hour:
        start = start + timedelta(days=1)
        return start.astimezone(timezone.utc)
    return now


def response_window_seconds(quote: QuoteRequest, config: QuoteDispatchConfig) -> int:
    minutes = (
        config.urgent_response_window_minutes
        if quote.is_urgent
        else config.response_window_minutes
    )
    return max(60, minutes * 60)


def _schedule_at(
    now: datetime, quote: QuoteRequest, config: QuoteDispatchConfig, delta: timedelta
) -> datetime | None:
    """Next evaluation time, shifted into a normal sending window if needed."""
    target = now + delta
    if not quote.is_urgent and not is_daytime(target, config):
        target = next_day_window(target, config)
    expires_at = _as_utc(quote.expires_at)
    if expires_at is not None and target >= expires_at:
        return None
    return target


def _can_send_now(quote: QuoteRequest, config: QuoteDispatchConfig, now: datetime) -> bool:
    if is_daytime(now, config):
        return True
    # Urgent requests may always go out at night when enabled. 24h businesses are
    # preferred by the candidate ladder, but all owners remain a fallback so the
    # request is never silently stuck until morning.
    return bool(quote.is_urgent and config.allow_urgent_at_night)


def _distance_band(
    quote: QuoteRequest, business: Business, config: QuoteDispatchConfig
) -> int:
    """0 tight radius, 1 expanded radius, 2 outside / unknown, 3 excluded."""
    if quote.geo_lat is None or quote.geo_lng is None:
        return 0
    if business.geo_lat is None or business.geo_lng is None:
        return 2 if config.fallback_outside_radius else 3
    distance = _haversine_km(
        quote.geo_lat, quote.geo_lng, business.geo_lat, business.geo_lng
    )
    if distance <= config.dispatch_radius_km:
        return 0
    if distance <= config.expand_radius_km:
        return 1
    return 2 if config.fallback_outside_radius else 3


async def _contacted_business_ids(session: AsyncSession, quote_id) -> set:
    delivered = set(
        (
            await session.execute(
                sa.select(QuoteDelivery.business_id).where(
                    QuoteDelivery.request_id == quote_id
                )
            )
        ).scalars().all()
    )
    offered = set(
        (
            await session.execute(
                sa.select(Offer.business_id).where(Offer.request_id == quote_id)
            )
        ).scalars().all()
    )
    return delivered | offered


async def _eligible_candidates(
    session: AsyncSession,
    quote: QuoteRequest,
    config: QuoteDispatchConfig,
    now: datetime,
) -> list[tuple[Business, int, int]]:
    """Return (business, radius_band, subcategory_rank) sorted by priority."""
    stmt = sa.select(Business).where(
        Business.category_id == quote.category_id,
        Business.status == BusinessStatus.APPROVED,
        Business.deleted_at.is_(None),
        Business.owner_id != quote.customer_id,
    )
    businesses = list((await session.execute(stmt)).scalars().all())
    if not businesses:
        return []

    contacted = await _contacted_business_ids(session, quote.id)
    contacted_owners = set(
        (
            await session.execute(
                sa.select(Business.owner_id)
                .join(QuoteDelivery, QuoteDelivery.business_id == Business.id)
                .where(QuoteDelivery.request_id == quote.id)
            )
        ).scalars().all()
    ) | set(
        (
            await session.execute(
                sa.select(Business.owner_id)
                .join(Offer, Offer.business_id == Business.id)
                .where(Offer.request_id == quote.id)
            )
        ).scalars().all()
    )
    businesses = [
        business
        for business in businesses
        if business.id not in contacted and business.owner_id not in contacted_owners
    ]
    if not businesses:
        return []

    # Spread requests across owners instead of always choosing the same top
    # rated business. 30 days is long enough to smooth weekly patterns.
    ids = [business.id for business in businesses]
    load_rows = (
        await session.execute(
            sa.select(QuoteDelivery.business_id, sa.func.count(QuoteDelivery.id))
            .where(
                QuoteDelivery.business_id.in_(ids),
                QuoteDelivery.sent_at >= now - timedelta(days=30),
            )
            .group_by(QuoteDelivery.business_id)
        )
    ).all()
    load = {business_id: int(count) for business_id, count in load_rows}

    ranked: list[tuple[Business, int, int]] = []
    for business in businesses:
        if (
            not config.subcategory_fallback
            and quote.subcategory_id is not None
            and business.subcategory_id != quote.subcategory_id
        ):
            continue
        band = _distance_band(quote, business, config)
        if band >= 3:
            continue
        subcategory_rank = (
            0
            if quote.subcategory_id is None
            or business.subcategory_id == quote.subcategory_id
            else 1
        )
        ranked.append((business, band, subcategory_rank))

    night = not is_daytime(now, config)
    ranked.sort(
        key=lambda item: (
            # Urgent night waves prefer 24h businesses. If none exist, the
            # regular owners are the fallback rather than waiting until morning.
            0 if not night or item[0].is_24h else 1,
            item[2],
            item[1],
            -(item[0].rating_avg or 0),
            -int(item[0].is_verified),
            load.get(item[0].id, 0),
            str(item[0].id),
        )
    )
    # A quote targets owners, not businesses. If one owner has several
    # businesses, only the best-ranked one is selected so they receive one
    # notification and the request does not consume several wave slots.
    unique: list[tuple[Business, int, int]] = []
    seen_owners: set = set()
    for item in ranked:
        if item[0].owner_id in seen_owners:
            continue
        seen_owners.add(item[0].owner_id)
        unique.append(item)
    return unique


def _wave_24h_pool(
    ranked: list[tuple[Business, int, int]],
    quote: QuoteRequest,
    config: QuoteDispatchConfig,
    now: datetime,
) -> list[tuple[Business, int, int]]:
    if not quote.is_urgent or is_daytime(now, config):
        return ranked
    twenty_four = [item for item in ranked if item[0].is_24h]
    return twenty_four if twenty_four else ranked


async def _deliver_to(
    session: AsyncSession,
    quote: QuoteRequest,
    businesses: list[Business],
    *,
    now: datetime,
    round_no: int,
    source: str,
) -> list[Business]:
    delivered: list[Business] = []
    notified_owners: set = set()
    for business in businesses:
        session.add(
            QuoteDelivery(
                request_id=quote.id,
                business_id=business.id,
                sent_at=now,
                round=round_no,
                source=source,
            )
        )
        if business.owner_id not in notified_owners:
            await notify_quote_request(
                session,
                owner_id=business.owner_id,
                quote_id=quote.id,
                title=quote.title,
                is_urgent=quote.is_urgent,
            )
            notified_owners.add(business.owner_id)
        delivered.append(business)
    return delivered


async def _record_run(
    session: AsyncSession,
    quote: QuoteRequest,
    *,
    round_no: int,
    trigger: str,
    candidate_count: int,
    delivered_count: int,
    detail: dict,
) -> None:
    session.add(
        QuoteDispatchRun(
            request_id=quote.id,
            round=round_no,
            trigger=trigger,
            candidate_count=candidate_count,
            delivered_count=delivered_count,
            detail=detail,
        )
    )


async def _finish_wave(
    session: AsyncSession,
    quote: QuoteRequest,
    config: QuoteDispatchConfig,
    *,
    now: datetime,
    delivered: list[Business],
    candidate_count: int,
    trigger: str,
    remaining_candidates: int,
    detail: dict,
) -> list[Business]:
    if not delivered:
        quote.last_dispatched_at = now
        quote.dispatch_status = "searching"
        # No candidate now does not mean no candidate forever: the platform is
        # local and a business may be approved minutes later. Keep a lightweight
        # scan scheduled without burning a delivery round or notifying anyone.
        quote.next_dispatch_at = _schedule_at(
            now,
            quote,
            config,
            timedelta(minutes=config.no_candidate_retry_minutes),
        )
        if quote.next_dispatch_at is None:
            quote.dispatch_status = "exhausted"
        await _record_run(
            session,
            quote,
            round_no=quote.dispatch_round,
            trigger=trigger,
            candidate_count=candidate_count,
            delivered_count=0,
            detail={**detail, "result": "no_candidate"},
        )
        return []

    quote.dispatch_round += 1
    quote.last_dispatched_at = now
    quote.dispatch_status = "active"
    round_no = quote.dispatch_round
    await _record_run(
        session,
        quote,
        round_no=round_no,
        trigger=trigger,
        candidate_count=candidate_count,
        delivered_count=len(delivered),
        detail={
            **detail,
            "result": "delivered",
            "business_ids": [str(business.id) for business in delivered],
        },
    )

    if quote.dispatch_round >= config.max_rounds or remaining_candidates == 0:
        quote.dispatch_status = "exhausted"
        quote.next_dispatch_at = None
        return delivered

    window = timedelta(seconds=response_window_seconds(quote, config))
    quote.next_dispatch_at = _schedule_at(now, quote, config, window)
    if quote.next_dispatch_at is None:
        quote.dispatch_status = "exhausted"
    return delivered


def _detail(
    *,
    batch_size: int,
    radius_used: str,
    subcategory_fallback_used: bool,
    radius_expanded: bool,
    outside_radius_used: bool,
) -> dict:
    return {
        "batch_size": batch_size,
        "radius_used": radius_used,
        "subcategory_fallback_used": subcategory_fallback_used,
        "radius_expanded": radius_expanded,
        "outside_radius_used": outside_radius_used,
    }


async def dispatch_quote(
    session: AsyncSession,
    quote: QuoteRequest,
    now: datetime | None = None,
    *,
    trigger: str = "initial",
    force: bool = False,
) -> list[Business]:
    """Run the next automatic wave for a freshly created or due quote.

    Returns the businesses actually targeted. The quote's dispatch columns are
    updated in the caller's transaction.
    """
    now = now or datetime.now(timezone.utc)
    config = await get_quote_dispatch_config(session)
    if quote.status != ACTIVE:
        quote.dispatch_status = COMPLETED
        quote.next_dispatch_at = None
        return []
    if not config.enabled:
        quote.dispatch_status = "disabled"
        quote.next_dispatch_at = None
        return []

    if not _can_send_now(quote, config, now):
        quote.dispatch_status = "scheduled"
        quote.next_dispatch_at = next_day_window(now, config)
        return []

    batch_size = (
        config.initial_batch_size if quote.dispatch_round == 0 else config.retry_batch_size
    )
    ranked = await _eligible_candidates(session, quote, config, now)
    candidate_count = len(ranked)
    pool = _wave_24h_pool(ranked, quote, config, now)
    selected = pool[:batch_size]
    if len(selected) < config.min_target_deliveries:
        selected_ids = {item[0].id for item in selected}
        for item in pool:
            if len(selected) >= config.min_target_deliveries:
                break
            if item[0].id not in selected_ids:
                selected.append(item)
                selected_ids.add(item[0].id)
    businesses = [item[0] for item in selected]
    remaining = max(0, candidate_count - len(businesses))

    bands = {item[1] for item in selected}
    radius_expanded = 1 in bands or 2 in bands
    outside_radius = 2 in bands
    subcategory_fallback = bool(
        quote.subcategory_id
        and config.subcategory_fallback
        and any(
            business.subcategory_id != quote.subcategory_id for business in businesses
        )
    )
    radius_used = (
        "outside"
        if outside_radius
        else "expanded"
        if radius_expanded
        else "tight"
    )
    delivered = await _deliver_to(
        session,
        quote,
        businesses,
        now=now,
        round_no=quote.dispatch_round + 1,
        source="auto",
    )
    quote.next_dispatch_at = None
    return await _finish_wave(
        session,
        quote,
        config,
        now=now,
        delivered=delivered,
        candidate_count=candidate_count,
        trigger=trigger,
        remaining_candidates=remaining,
        detail=_detail(
            batch_size=batch_size,
            radius_used=radius_used,
            subcategory_fallback_used=subcategory_fallback,
            radius_expanded=radius_expanded,
            outside_radius_used=outside_radius,
        ),
    )


async def retry_due_quote(
    session: AsyncSession,
    quote: QuoteRequest,
    now: datetime | None = None,
    *,
    force: bool = False,
) -> list[Business]:
    """Evaluate engagement and send a new wave only when another wave is due.

    A wave with a pending offer stops automatic expansion. A silent wave expands
    to new owners. A seen-but-no-offer wave expands only when the dashboard
    setting says so; otherwise it waits until the quote expires (or a later
    manual dispatch).
    """
    now = now or datetime.now(timezone.utc)
    config = await get_quote_dispatch_config(session)

    if quote.status != ACTIVE:
        quote.dispatch_status = COMPLETED
        quote.next_dispatch_at = None
        return []
    if not config.enabled:
        quote.dispatch_status = "disabled"
        quote.next_dispatch_at = None
        return []
    if not _can_send_now(quote, config, now):
        quote.dispatch_status = "scheduled"
        quote.next_dispatch_at = next_day_window(now, config)
        return []

    pending_offer = (
        await session.execute(
            sa.select(Offer.id).where(
                Offer.request_id == quote.id,
                Offer.status == "pending",
                Offer.deleted_at.is_(None),
            ).limit(1)
        )
    ).scalar()
    if pending_offer is not None:
        quote.dispatch_status = "offers"
        quote.next_dispatch_at = None
        return []

    if quote.dispatch_round >= config.max_rounds and not force:
        quote.dispatch_status = "exhausted"
        quote.next_dispatch_at = None
        return []

    latest_round = quote.dispatch_round
    latest = []
    if latest_round:
        latest = list(
            (
                await session.execute(
                    sa.select(QuoteDelivery).where(
                        QuoteDelivery.request_id == quote.id,
                        QuoteDelivery.round == latest_round,
                    )
                )
            ).scalars().all()
        )
    engaged = any(
        delivery.seen_at is not None or delivery.responded_at is not None
        for delivery in latest
    )
    responded = any(delivery.responded_at is not None for delivery in latest)
    if engaged and not responded and not config.advance_on_seen and not force:
        # Looking at the request is engagement, but there is still no offer.
        # Keep the quote active and check again after one response window.
        window = timedelta(seconds=response_window_seconds(quote, config))
        quote.dispatch_status = "active"
        quote.next_dispatch_at = _schedule_at(now, quote, config, window)
        return []

    return await dispatch_quote(
        session, quote, now, trigger="forced" if force else "retry", force=force
    )


async def dispatch_manual_businesses(
    session: AsyncSession,
    quote: QuoteRequest,
    businesses: list[Business],
    *,
    now: datetime | None = None,
    actor_id: uuid.UUID | None = None,
) -> list[Business]:
    """Assign specific approved businesses, bypassing category/radius logic."""
    now = now or datetime.now(timezone.utc)
    config = await get_quote_dispatch_config(session)
    if quote.status != ACTIVE:
        return []
    contacted = await _contacted_business_ids(session, quote.id)
    selected = [
        business
        for business in businesses
        if business.id not in contacted
        and business.status == BusinessStatus.APPROVED
        and business.deleted_at is None
    ]
    delivered = await _deliver_to(
        session,
        quote,
        selected,
        now=now,
        round_no=quote.dispatch_round + 1,
        source="manual",
    )
    if delivered:
        quote.dispatch_round += 1
        quote.last_dispatched_at = now
        # Manual assignment restarts the response window unless a pending offer
        # already stopped automatic expansion or the auto round budget is spent.
        pending_offer = (
            await session.execute(
                sa.select(Offer.id).where(
                    Offer.request_id == quote.id,
                    Offer.status == "pending",
                    Offer.deleted_at.is_(None),
                ).limit(1)
            )
        ).scalar()
        if pending_offer is not None:
            quote.dispatch_status = "offers"
            quote.next_dispatch_at = None
        elif quote.dispatch_round < config.max_rounds:
            quote.dispatch_status = "active"
            quote.next_dispatch_at = _schedule_at(
                now,
                quote,
                config,
                timedelta(seconds=response_window_seconds(quote, config)),
            )
        else:
            quote.dispatch_status = "exhausted"
            quote.next_dispatch_at = None
    await _record_run(
        session,
        quote,
        round_no=quote.dispatch_round,
        trigger="manual",
        candidate_count=len(businesses),
        delivered_count=len(delivered),
        detail={
            "result": "delivered" if delivered else "no_new_business",
            "actor_id": str(actor_id) if actor_id else None,
            "business_ids": [str(business.id) for business in delivered],
            "skipped_business_ids": [
                str(business.id)
                for business in businesses
                if business.id not in {item.id for item in delivered}
            ],
        },
    )
    return delivered


def expiry_for(is_urgent: bool, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now + (timedelta(hours=2) if is_urgent else timedelta(hours=24))
