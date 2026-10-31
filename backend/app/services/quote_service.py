"""Shared quote/offer helpers.

The customer and owner inboxes intentionally expose different fields. In
particular a customer phone number may never appear in an owner response until
that owner's business has won the request. Keeping serialization in one place
makes that rule auditable.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import QuoteDelivery
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.quote import Offer, QuoteRequest
from app.models.user import User
from app.services.quote_dispatch_settings import QuoteDispatchConfig, get_quote_dispatch_config

ACTIVE = "active"
ACCEPTED = "accepted"
CANCELLED = "cancelled"
EXPIRED = "expired"
PENDING = "pending"
DECLINED = "declined"

DISPATCH_RADIUS_KM = 10.0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def is_quote_expired(quote: QuoteRequest, now: datetime | None = None) -> bool:
    expires_at = as_utc(quote.expires_at)
    return bool(expires_at and expires_at <= (now or utc_now()))


async def expire_stale_quotes(session: AsyncSession, now: datetime | None = None) -> int:
    """Lazily expire requests (and their pending offers) before reads.

    A dedicated worker can call the same helper later; doing it on read keeps
    the UI honest without a hard dependency on the worker process.
    """
    now = now or utc_now()
    ids = list(
        (
            await session.execute(
                sa.select(QuoteRequest.id).where(
                    QuoteRequest.status == ACTIVE,
                    QuoteRequest.expires_at.is_not(None),
                    QuoteRequest.expires_at <= now,
                )
            )
        ).scalars().all()
    )
    if not ids:
        return 0
    await session.execute(
        sa.update(Offer)
        .where(Offer.request_id.in_(ids), Offer.status == PENDING)
        .values(status=EXPIRED)
    )
    await session.execute(
        sa.update(QuoteRequest)
        .where(QuoteRequest.id.in_(ids))
        .values(
            status=EXPIRED,
            dispatch_status="completed",
            next_dispatch_at=None,
        )
    )
    return len(ids)


def category_payload(category: Category | None) -> dict | None:
    if category is None:
        return None
    return {
        "id": category.id,
        "slug": category.slug,
        "name": category.name,
        "icon": category.icon,
    }


def subcategory_payload(subcategory: Subcategory | None) -> dict | None:
    if subcategory is None:
        return None
    return {
        "id": subcategory.id,
        "slug": subcategory.slug,
        "name": subcategory.name,
        "icon": subcategory.icon,
    }


def business_payload(business: Business | None, *, include_phone: bool = False) -> dict | None:
    if business is None:
        return None
    data = {
        "id": str(business.id),
        "slug": business.slug,
        "name": business.name,
        "address": business.address,
        "rating_avg": round(business.rating_avg or 0, 2),
        "rating_count": business.rating_count or 0,
        "is_verified": business.is_verified,
        "profile_image_url": business.profile_image_url,
        "category": category_payload(business.category),
    }
    if include_phone:
        data["phone_business"] = business.phone_business
    return data


def customer_payload(
    customer: User | None, *, include_phone: bool = False, phone: str | None = None
) -> dict | None:
    if customer is None:
        return None
    data = {
        "id": str(customer.id),
        "name": (customer.full_name or "").strip() or "کاربر نومکس",
    }
    if include_phone:
        data["phone"] = phone or customer.phone
    return data


def offer_payload(
    offer: Offer,
    *,
    business: Business | None = None,
    include_business_phone: bool = False,
) -> dict:
    return {
        "id": str(offer.id),
        "request_id": str(offer.request_id),
        "business_id": str(offer.business_id),
        "price": float(offer.price) if offer.price is not None else None,
        "unit": offer.unit,
        "brand": offer.brand,
        "message": offer.message,
        "status": offer.status,
        "business": business_payload(
            business or getattr(offer, "business", None),
            include_phone=include_business_phone,
        ),
        "created_at": offer.created_at.isoformat() if offer.created_at else None,
        "updated_at": offer.updated_at.isoformat() if offer.updated_at else None,
    }


def quote_payload(
    quote: QuoteRequest,
    *,
    offers_count: int = 0,
    accepted_offer: Offer | None = None,
    accepted_business: Business | None = None,
    customer: User | None = None,
    include_customer_phone: bool = False,
    dispatch: dict | None = None,
) -> dict:
    data = {
        "id": str(quote.id),
        "title": quote.title,
        "description": quote.description,
        "category": category_payload(getattr(quote, "category", None)),
        "subcategory": subcategory_payload(getattr(quote, "subcategory", None)),
        "address": quote.address,
        "neighborhood": quote.neighborhood,
        "geo": (
            {"lat": quote.geo_lat, "lng": quote.geo_lng}
            if quote.geo_lat is not None and quote.geo_lng is not None
            else None
        ),
        "is_urgent": quote.is_urgent,
        "status": quote.status,
        "expires_at": as_utc(quote.expires_at).isoformat() if quote.expires_at else None,
        "accepted_offer_id": str(quote.accepted_offer_id) if quote.accepted_offer_id else None,
        "offers_count": offers_count,
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
    }
    if dispatch is not None:
        data["dispatch"] = dispatch
    if accepted_offer is not None:
        data["accepted_offer"] = offer_payload(
            accepted_offer,
            business=accepted_business,
            include_business_phone=True,
        )
    if customer is not None:
        data["customer"] = customer_payload(
            customer, include_phone=include_customer_phone
        )
        if include_customer_phone:
            # Kept for owner/detail clients written against the v1 contract.
            data["customer_phone"] = customer.phone
    return data


async def dispatch_summaries(
    session: AsyncSession,
    quotes: list[QuoteRequest],
    config: QuoteDispatchConfig | None = None,
) -> dict:
    """Aggregate dispatch progress for customer/admin lists in one query.

    Customer payloads only ever receive counts and timing; owner identities are
    deliberately absent until a business submits an offer.
    """
    if not quotes:
        return {}
    config = config or await get_quote_dispatch_config(session)
    ids = [quote.id for quote in quotes]
    delivery_rows = (
        await session.execute(
            sa.select(
                QuoteDelivery.request_id,
                sa.func.count(QuoteDelivery.id),
                sa.func.count(QuoteDelivery.seen_at),
                sa.func.max(QuoteDelivery.round),
                sa.func.max(QuoteDelivery.sent_at),
            )
            .where(QuoteDelivery.request_id.in_(ids))
            .group_by(QuoteDelivery.request_id)
        )
    ).all()
    offer_rows = (
        await session.execute(
            sa.select(Offer.request_id, sa.func.count(Offer.id))
            .where(
                Offer.request_id.in_(ids),
                Offer.deleted_at.is_(None),
                Offer.status != DECLINED,
            )
            .group_by(Offer.request_id)
        )
    ).all()
    delivered = {
        request_id: (
            int(count),
            int(seen or 0),
            int(latest_round or 0),
            latest_sent,
        )
        for request_id, count, seen, latest_round, latest_sent in delivery_rows
    }
    offered = {request_id: int(count) for request_id, count in offer_rows}

    result: dict = {}
    for quote in quotes:
        count, seen, latest_round, latest_sent = delivered.get(quote.id, (0, 0, 0, None))
        offers = offered.get(quote.id, 0)
        if quote.status != ACTIVE:
            state = "closed"
        elif quote.dispatch_status == "scheduled":
            state = "scheduled"
        elif quote.dispatch_status == "searching":
            state = "searching"
        elif quote.dispatch_status == "offers" or offers:
            state = "offers"
        elif quote.dispatch_status == "disabled":
            state = "disabled"
        elif count == 0:
            state = (
                "exhausted"
                if quote.dispatch_status == "exhausted"
                else "pending"
            )
        elif seen == 0:
            state = "waiting_seen"
        else:
            state = "reviewing"
        result[quote.id] = {
            "state": state,
            "status": quote.dispatch_status,
            "round": quote.dispatch_round,
            "latest_round": latest_round,
            "max_rounds": config.max_rounds,
            "delivered_count": count,
            "seen_count": seen,
            "offers_count": offers,
            "min_target_deliveries": config.min_target_deliveries,
            "next_dispatch_at": (
                as_utc(quote.next_dispatch_at).isoformat()
                if quote.next_dispatch_at is not None
                else None
            ),
            "last_dispatched_at": (
                as_utc(quote.last_dispatched_at).isoformat()
                if quote.last_dispatched_at is not None
                else (as_utc(latest_sent).isoformat() if latest_sent else None)
            ),
            "is_active": quote.status == ACTIVE,
        }
    return result


async def offer_counts(session: AsyncSession, quote_ids: list) -> dict:
    if not quote_ids:
        return {}
    rows = (
        await session.execute(
            sa.select(Offer.request_id, sa.func.count(Offer.id))
            .where(
                Offer.request_id.in_(quote_ids),
                Offer.deleted_at.is_(None),
                Offer.status != DECLINED,
            )
            .group_by(Offer.request_id)
        )
    ).all()
    return {request_id: int(count) for request_id, count in rows}


async def offers_by_id(
    session: AsyncSession, offer_ids: list
) -> dict:
    if not offer_ids:
        return {}
    rows = (
        await session.execute(sa.select(Offer).where(Offer.id.in_(offer_ids)))
    ).scalars().all()
    return {offer.id: offer for offer in rows}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def business_matches_quote(business: Business, quote: QuoteRequest) -> bool:
    if business.deleted_at is not None:
        return False
    if business.status != BusinessStatus.APPROVED:
        return False
    if business.category_id != quote.category_id:
        return False
    if quote.subcategory_id is not None and business.subcategory_id != quote.subcategory_id:
        return False
    if quote.geo_lat is not None and quote.geo_lng is not None:
        if business.geo_lat is None or business.geo_lng is None:
            return False
        if (
            haversine_km(quote.geo_lat, quote.geo_lng, business.geo_lat, business.geo_lng)
            > DISPATCH_RADIUS_KM
        ):
            return False
    return True


async def owned_businesses(session: AsyncSession, user_id) -> list[Business]:
    return list(
        (
            await session.execute(
                sa.select(Business).where(
                    Business.owner_id == user_id,
                    Business.deleted_at.is_(None),
                )
            )
        ).scalars().all()
    )


async def get_category(
    session: AsyncSession, category_id: int
) -> Category:
    category = await session.get(Category, category_id)
    if category is None or category.deleted_at is not None or not category.is_active:
        from app.core.errors import AppError

        raise AppError("not_found", "category_not_found", 404)
    return category


async def get_subcategory(
    session: AsyncSession, subcategory_id: int, category_id: int
) -> Subcategory:
    from app.core.errors import AppError

    subcategory = await session.get(Subcategory, subcategory_id)
    if (
        subcategory is None
        or subcategory.deleted_at is not None
        or subcategory.category_id != category_id
    ):
        raise AppError("validation_error", "subcategory_category_mismatch", 422)
    return subcategory
