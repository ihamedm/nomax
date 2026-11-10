import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.permissions import has_permission
from app.db.session import get_db
from app.models.analytics import QuoteDelivery
from app.models.business import Business
from app.models.quote import Offer, QuoteRequest
from app.models.user import User
from app.services.inapp_notifications import (
    notify_quote_accepted,
    notify_quote_cancelled,
    notify_quote_offer,
)
from app.services import quote_broker
from app.services.quote_dispatcher import dispatch_quote, expiry_for
from app.services.quote_service import (
    ACCEPTED,
    ACTIVE,
    CANCELLED,
    DECLINED,
    EXPIRED,
    PENDING,
    business_matches_quote,
    customer_payload,
    dispatch_summaries,
    expire_stale_quotes,
    get_category,
    get_subcategory,
    offer_counts,
    offer_payload,
    offers_by_id,
    owned_businesses,
    quote_payload,
)

router = APIRouter(tags=["quotes"])


def _clean(value: object, max_length: int) -> str:
    return str(value or "").strip()[:max_length]


def _parse_price(value: object) -> float:
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AppError("invalid_price", "invalid_price", 422)
    if price <= 0 or price > Decimal("999999999999"):
        raise AppError("invalid_price", "invalid_price", 422)
    return float(price)


def _parse_coordinates(payload: dict) -> tuple[float | None, float | None]:
    lat, lng = payload.get("geo_lat"), payload.get("geo_lng")
    if lat is None and lng is None:
        return None, None
    try:
        lat_f, lng_f = float(lat), float(lng)
    except (TypeError, ValueError):
        raise AppError("validation_error", "invalid_coordinates", 422)
    if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
        raise AppError("validation_error", "invalid_coordinates", 422)
    return lat_f, lng_f


async def _get_quote(
    session: AsyncSession, quote_id: str, *, lock: bool = False
) -> QuoteRequest:
    try:
        qid = uuid.UUID(quote_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    stmt = sa.select(QuoteRequest).where(QuoteRequest.id == qid)
    if lock:
        # Postgres cannot lock the nullable side of the eager-loaded outer
        # joins. Lock only the request row; callers that lock do not serialize
        # category/customer relationships.
        stmt = stmt.options(lazyload("*")).with_for_update()
    quote = (await session.execute(stmt)).scalars().first()
    if quote is None or quote.deleted_at is not None:
        raise AppError("not_found", "quote_not_found", 404)
    return quote


def _check_not_expired(quote: QuoteRequest) -> None:
    if quote.status != ACTIVE:
        raise AppError("conflict", "quote_not_active", 409)
    expires_at = quote.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        quote.status = EXPIRED
        raise AppError("conflict", "quote_expired", 409)


async def _commit_or_conflict(session: AsyncSession, code: str) -> None:
    try:
        await session.commit()
    except IntegrityError:
        # Concurrent creates can race past the application-level checks; the
        # partial unique index remains the source of truth.
        await session.rollback()
        raise AppError(code, code, 409)


async def _expire_other_offers(
    session: AsyncSession, quote_id, accepted_offer_id
) -> None:
    offers = (
        await session.execute(
            sa.select(Offer).where(
                Offer.request_id == quote_id,
                Offer.id != accepted_offer_id,
                Offer.status == PENDING,
            )
        )
    ).scalars().all()
    for offer in offers:
        offer.status = EXPIRED


@router.post("/quotes/requests")
@router.post("/quotes")
async def create_quote(
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    title = _clean(payload.get("title") or payload.get("item_description"), 160)
    address = _clean(payload.get("address"), 255)
    description = _clean(payload.get("description"), 2000) or None
    neighborhood = _clean(payload.get("neighborhood"), 120) or None
    if not title or payload.get("category_id") is None or not address:
        raise AppError("validation_error", "title_address_category_required", 422)
    if len(title) < 3:
        raise AppError("validation_error", "title_too_short", 422)
    if len(address) < 5:
        raise AppError("validation_error", "address_too_short", 422)

    try:
        category_id = int(payload["category_id"])
        subcategory_id = (
            int(payload["subcategory_id"])
            if payload.get("subcategory_id") is not None
            else None
        )
    except (TypeError, ValueError):
        raise AppError("validation_error", "invalid_category_id", 422)
    category = await get_category(session, category_id)
    subcategory = None
    if subcategory_id is not None:
        subcategory = await get_subcategory(session, subcategory_id, category.id)
    geo_lat, geo_lng = _parse_coordinates(payload)

    await expire_stale_quotes(session)
    existing = (
        await session.execute(
            sa.select(QuoteRequest).where(
                QuoteRequest.customer_id == user.id,
                QuoteRequest.status == ACTIVE,
                QuoteRequest.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if existing is not None:
        _check_not_expired(existing)
        raise AppError(
            "conflict",
            "active_quote_exists",
            409,
            {"quote_id": str(existing.id)},
        )

    is_urgent = bool(payload.get("is_urgent", False))
    quote = QuoteRequest(
        customer_id=user.id,
        category_id=category.id,
        subcategory_id=subcategory.id if subcategory else None,
        title=title,
        description=description,
        address=address,
        neighborhood=neighborhood,
        geo_lat=geo_lat,
        geo_lng=geo_lng,
        is_urgent=is_urgent,
        status=ACTIVE,
        expires_at=expiry_for(is_urgent),
    )
    quote.category = category
    quote.subcategory = subcategory
    quote.customer = user
    session.add(quote)
    await session.flush()
    await dispatch_quote(session, quote)
    await _commit_or_conflict(session, "active_quote_exists")
    if quote.next_dispatch_at is not None:
        try:
            await quote_broker.schedule_retry(quote.id, quote.next_dispatch_at)
        except Exception:  # noqa: BLE001 - DB schedule remains authoritative
            pass

    saved = (
        await session.execute(sa.select(QuoteRequest).where(QuoteRequest.id == quote.id))
    ).scalars().one()
    summaries = await dispatch_summaries(session, [saved])
    return {"data": quote_payload(saved, dispatch=summaries.get(saved.id))}


@router.get("/quotes/requests/mine")
async def my_quotes(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    await expire_stale_quotes(session)
    rows = (
        await session.execute(
            sa.select(QuoteRequest)
            .where(QuoteRequest.customer_id == user.id, QuoteRequest.deleted_at.is_(None))
            .order_by(QuoteRequest.created_at.desc())
        )
    ).scalars().all()

    counts = await offer_counts(session, [q.id for q in rows])
    accepted_ids = [q.accepted_offer_id for q in rows if q.accepted_offer_id]
    accepted_offers = await offers_by_id(session, accepted_ids)
    business_ids = {o.business_id for o in accepted_offers.values()}
    businesses = {}
    if business_ids:
        businesses = {
            business.id: business
            for business in (
                await session.execute(sa.select(Business).where(Business.id.in_(business_ids)))
            ).scalars().all()
        }

    summaries = await dispatch_summaries(session, rows)
    items = []
    for quote in rows:
        accepted = accepted_offers.get(quote.accepted_offer_id)
        items.append(
            quote_payload(
                quote,
                offers_count=counts.get(quote.id, 0),
                accepted_offer=accepted,
                accepted_business=businesses.get(accepted.business_id) if accepted else None,
                dispatch=summaries.get(quote.id),
            )
        )
    return {"data": {"items": items}}


@router.get("/quotes/requests/incoming")
async def incoming_quotes(
    scope: Literal["new", "archive", "customers"] = Query("new"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    await expire_stale_quotes(session)
    my_businesses = await owned_businesses(session, user.id)
    if not my_businesses:
        return {
            "data": {
                "scope": scope,
                "counts": {"new": 0, "archive": 0, "customers": 0},
                "items": [],
            }
        }

    business_by_id = {business.id: business for business in my_businesses}
    delivery_rows = (
        await session.execute(
            sa.select(QuoteDelivery.request_id, QuoteDelivery.business_id).where(
                QuoteDelivery.business_id.in_(list(business_by_id))
            )
        )
    ).all()
    delivered_quote_ids = {row[0] for row in delivery_rows}

    offer_rows = (
        await session.execute(
            sa.select(Offer, QuoteRequest, Business)
            .join(QuoteRequest, Offer.request_id == QuoteRequest.id)
            .join(Business, Offer.business_id == Business.id)
            .where(
                Business.owner_id == user.id,
                Offer.deleted_at.is_(None),
                QuoteRequest.deleted_at.is_(None),
            )
            .order_by(Offer.updated_at.desc())
        )
    ).all()

    customer_map: dict = {}
    archive_map: dict = {}
    offered_quote_ids: set = set()
    archive_rank = {PENDING: 0, DECLINED: 1, EXPIRED: 2, "rejected": 3}

    for offer, quote, business in offer_rows:
        offered_quote_ids.add(quote.id)
        entry = (offer, business, quote)
        if offer.status == ACCEPTED:
            customer_map[quote.id] = entry
            continue
        current = archive_map.get(quote.id)
        if current is None or archive_rank.get(offer.status, 9) < archive_rank.get(
            current[0].status, 9
        ):
            archive_map[quote.id] = entry

    def matching_for(quote: QuoteRequest) -> list[Business]:
        # A request explicitly dispatched to one of this owner's businesses is
        # always visible, even when the fallback ladder had to widen the
        # subcategory or radius. Otherwise the owner would receive a
        # notification for a request they cannot open or answer.
        matches = [b for b in my_businesses if business_matches_quote(b, quote)]
        match_ids = {business.id for business in matches}
        for request_id, business_id in delivery_rows:
            if request_id == quote.id and business_id in business_by_id:
                if business_id not in match_ids:
                    matches.append(business_by_id[business_id])
                    match_ids.add(business_id)
        return matches

    def owner_item(
        quote: QuoteRequest,
        *,
        businesses: list[Business],
        offer: Offer | None = None,
        business: Business | None = None,
        include_customer_phone: bool = False,
    ) -> dict:
        data = quote_payload(quote)
        data["customer"] = customer_payload(
            quote.customer, include_phone=include_customer_phone
        )
        if include_customer_phone and quote.customer is not None:
            data["customer_phone"] = quote.customer.phone
        data["matching_businesses"] = [
            {"id": str(item.id), "name": item.name} for item in businesses
        ]
        if offer is not None:
            data["my_offer"] = offer_payload(offer, business=business)
        return data

    # New = active requests in which none of this owner's businesses has bid yet.
    category_ids = {b.category_id for b in my_businesses}
    candidate_quotes = (
        await session.execute(
            sa.select(QuoteRequest)
            .where(
                QuoteRequest.status == ACTIVE,
                QuoteRequest.deleted_at.is_(None),
                sa.or_(
                    QuoteRequest.category_id.in_(category_ids),
                    QuoteRequest.id.in_(delivered_quote_ids),
                ),
            )
            .order_by(QuoteRequest.created_at.desc())
            .limit(100)
        )
    ).scalars().all()

    new_items = []
    new_matches: dict[uuid.UUID, list[uuid.UUID]] = {}
    for quote in candidate_quotes:
        if quote.id in offered_quote_ids:
            continue
        businesses = matching_for(quote)
        if not businesses:
            continue
        new_items.append(owner_item(quote, businesses=businesses))
        new_matches[quote.id] = [business.id for business in businesses]
        if len(new_items) >= 50:
            break

    # Rendering a delivered request marks that actual delivery as seen. We do
    # not invent delivery rows for other category owners who merely browse the
    # inbox: dispatch waves and response metrics must remain auditable.
    if scope == "new" and new_items:
        now = datetime.now(timezone.utc)
        await session.execute(
            sa.update(QuoteDelivery)
            .where(
                QuoteDelivery.request_id.in_(list(new_matches)),
                QuoteDelivery.business_id.in_([b.id for b in my_businesses]),
                QuoteDelivery.seen_at.is_(None),
            )
            .values(seen_at=now),
        )

    archive_items = [
        owner_item(quote, businesses=[business], offer=offer, business=business)
        for offer, business, quote in archive_map.values()
    ]
    customer_items = [
        owner_item(
            quote,
            businesses=[business],
            offer=offer,
            business=business,
            include_customer_phone=True,
        )
        for offer, business, quote in customer_map.values()
    ]
    archive_items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    customer_items.sort(key=lambda item: item.get("created_at") or "", reverse=True)

    items = {"new": new_items, "archive": archive_items, "customers": customer_items}[scope]
    return {
        "data": {
            "scope": scope,
            "counts": {
                "new": len(new_items),
                "archive": len(archive_items),
                "customers": len(customer_items),
            },
            "items": items,
        }
    }


@router.post("/quotes/requests/{quote_id}/cancel")
async def cancel_quote(
    quote_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    quote = await _get_quote(session, quote_id)
    if quote.customer_id != user.id:
        raise AppError("forbidden", "not_quote_owner", 403)
    if quote.status != ACTIVE:
        raise AppError("conflict", "quote_not_cancellable", 409)

    pending_offers = (
        await session.execute(
            sa.select(Offer).where(
                Offer.request_id == quote.id,
                Offer.status == PENDING,
                Offer.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for offer in pending_offers:
        offer.status = EXPIRED
        business = await session.get(Business, offer.business_id)
        if business is not None:
            await notify_quote_cancelled(
                session,
                owner_id=business.owner_id,
                quote_id=quote.id,
                title=quote.title,
            )
    quote.status = CANCELLED
    quote.dispatch_status = "completed"
    quote.next_dispatch_at = None
    await session.commit()
    try:
        await quote_broker.clear_retry(quote.id)
    except Exception:  # noqa: BLE001 - DB state is authoritative
        pass
    await session.refresh(quote)
    counts = await offer_counts(session, [quote.id])
    return {"data": quote_payload(quote, offers_count=counts.get(quote.id, 0))}


@router.get("/quotes/{quote_id}")
async def get_quote(
    quote_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    quote = await _get_quote(session, quote_id)
    if quote.status == ACTIVE:
        await expire_stale_quotes(session)
        await session.refresh(quote)

    is_customer = quote.customer_id == user.id
    is_admin = has_permission(user, "quote.read")
    my_businesses = await owned_businesses(session, user.id)
    owned_ids = {b.id for b in my_businesses}

    offer_rows = (
        await session.execute(
            sa.select(Offer).where(
                Offer.request_id == quote.id,
                Offer.deleted_at.is_(None),
            )
        )
    ).scalars().all()

    if not is_customer and not is_admin:
        visible_offers = [offer for offer in offer_rows if offer.business_id in owned_ids]
        if not visible_offers:
            raise AppError("not_found", "quote_not_found", 404)
    else:
        visible_offers = offer_rows

    if is_customer:
        visible_offers = [offer for offer in visible_offers if offer.status != DECLINED]

    accepted = next(
        (offer for offer in offer_rows if offer.id == quote.accepted_offer_id), None
    )
    accepted_business = (
        await session.get(Business, accepted.business_id) if accepted is not None else None
    )
    customer: User | None = None
    phone_visible = False
    if is_admin:
        customer = await session.get(User, quote.customer_id)
        phone_visible = True
    elif not is_customer:
        customer = await session.get(User, quote.customer_id)
        phone_visible = quote.phone_revealed_to in owned_ids

    dispatch = None
    if is_customer or is_admin:
        summaries = await dispatch_summaries(session, [quote])
        dispatch = summaries.get(quote.id)
    data = quote_payload(
        quote,
        offers_count=len([offer for offer in offer_rows if offer.status != DECLINED]),
        accepted_offer=accepted,
        accepted_business=accepted_business,
        customer=customer,
        include_customer_phone=phone_visible,
        dispatch=dispatch,
    )
    if is_customer:
        data.pop("customer", None)
    data["offers"] = [
        offer_payload(
            offer,
            include_business_phone=bool(
                accepted is not None and offer.id == accepted.id
            )
            or is_admin
            or (not is_customer and offer.business_id in owned_ids),
        )
        for offer in sorted(
            visible_offers,
            key=lambda offer: (
                offer.id != quote.accepted_offer_id,
                offer.status != PENDING,
                offer.price is None,
                float(offer.price) if offer.price is not None else 0,
            ),
        )
    ]
    return {"data": data}


@router.post("/quotes/offers")
@router.post("/quotes/{quote_id}/offers")
async def create_offer(
    payload: dict,
    quote_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    raw_id = quote_id or payload.get("request_id")
    if not raw_id:
        raise AppError("validation_error", "request_id_required", 422)
    quote = await _get_quote(session, str(raw_id))
    _check_not_expired(quote)

    try:
        business_id = uuid.UUID(str(payload.get("business_id")))
    except (ValueError, TypeError):
        raise AppError("validation_error", "invalid_business_id", 422)
    business = await session.get(Business, business_id)
    if business is None or business.owner_id != user.id:
        raise AppError("forbidden", "business_not_owned", 403)
    dispatched = (
        await session.execute(
            sa.select(QuoteDelivery.id).where(
                QuoteDelivery.request_id == quote.id,
                QuoteDelivery.business_id == business.id,
            )
        )
    ).scalar()
    if not business_matches_quote(business, quote) and dispatched is None:
        raise AppError("validation_error", "business_category_mismatch", 422)

    existing = (
        await session.execute(
            sa.select(Offer).where(
                Offer.request_id == quote.id,
                Offer.business_id == business.id,
            )
        )
    ).scalars().first()
    if existing is not None:
        raise AppError("offer_already_submitted", "offer_already_submitted", 409)

    price = _parse_price(payload.get("price"))
    unit = _clean(payload.get("unit") or "کل کار", 30) or "کل کار"
    brand = _clean(payload.get("brand"), 120) or None
    message = _clean(payload.get("message") or payload.get("notes"), 1000) or None

    offer = Offer(
        request_id=quote.id,
        business_id=business.id,
        price=price,
        unit=unit,
        brand=brand,
        message=message,
        status=PENDING,
    )
    offer.business = business
    session.add(offer)
    delivery = (
        await session.execute(
            sa.select(QuoteDelivery).where(
                QuoteDelivery.request_id == quote.id,
                QuoteDelivery.business_id == business.id,
            )
        )
    ).scalars().first()
    now = datetime.now(timezone.utc)
    if delivery is not None:
        delivery.responded_at = now
    quote.dispatch_status = "offers"
    quote.next_dispatch_at = None
    await notify_quote_offer(
        session,
        customer_id=quote.customer_id,
        quote_id=quote.id,
        business_name=business.name,
        price=price,
    )
    await _commit_or_conflict(session, "offer_already_submitted")
    try:
        await quote_broker.clear_retry(quote.id)
    except Exception:  # noqa: BLE001
        pass

    saved = (
        await session.execute(sa.select(Offer).where(Offer.id == offer.id))
    ).scalars().one()
    return {"data": offer_payload(saved)}


@router.post("/quotes/requests/{quote_id}/decline")
async def decline_quote(
    quote_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    quote = await _get_quote(session, quote_id)
    _check_not_expired(quote)

    try:
        business_id = uuid.UUID(str(payload.get("business_id")))
    except (ValueError, TypeError):
        raise AppError("validation_error", "invalid_business_id", 422)
    business = await session.get(Business, business_id)
    if business is None or business.owner_id != user.id:
        raise AppError("forbidden", "business_not_owned", 403)
    dispatched = (
        await session.execute(
            sa.select(QuoteDelivery.id).where(
                QuoteDelivery.request_id == quote.id,
                QuoteDelivery.business_id == business.id,
            )
        )
    ).scalar()
    if not business_matches_quote(business, quote) and dispatched is None:
        raise AppError("validation_error", "business_category_mismatch", 422)

    existing = (
        await session.execute(
            sa.select(Offer).where(
                Offer.request_id == quote.id, Offer.business_id == business.id
            )
        )
    ).scalars().first()
    if existing is not None:
        raise AppError("offer_already_submitted", "offer_already_submitted", 409)

    offer = Offer(
        request_id=quote.id,
        business_id=business.id,
        status=DECLINED,
    )
    offer.business = business
    session.add(offer)
    delivery = (
        await session.execute(
            sa.select(QuoteDelivery).where(
                QuoteDelivery.request_id == quote.id,
                QuoteDelivery.business_id == business.id,
            )
        )
    ).scalars().first()
    if delivery is not None:
        delivery.responded_at = datetime.now(timezone.utc)
    await _commit_or_conflict(session, "offer_already_submitted")
    return {
        "data": {
            "request_id": str(quote.id),
            "business_id": str(business.id),
            "status": DECLINED,
        }
    }


@router.patch("/quotes/offers/{offer_id}/accept")
@router.post("/quotes/{quote_id}/offers/{offer_id}/accept")
async def accept_offer(
    offer_id: str,
    quote_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        oid = uuid.UUID(offer_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    offer = await session.get(Offer, oid)
    if offer is None or offer.deleted_at is not None:
        raise AppError("not_found", "offer_not_found", 404)
    if quote_id and str(offer.request_id) != quote_id:
        raise AppError("not_found", "offer_not_found", 404)

    quote = await _get_quote(session, str(offer.request_id), lock=True)
    if quote.customer_id != user.id:
        raise AppError("forbidden", "not_quote_owner", 403)
    _check_not_expired(quote)

    if offer.status == ACCEPTED and quote.accepted_offer_id == offer.id:
        return {"data": offer_payload(offer)}
    if offer.status != PENDING:
        raise AppError("conflict", "offer_not_pending", 409)

    quote.status = ACCEPTED
    quote.accepted_offer_id = offer.id
    quote.phone_revealed_to = offer.business_id
    quote.accepted_at = datetime.now(timezone.utc)
    quote.dispatch_status = "completed"
    quote.next_dispatch_at = None
    offer.status = ACCEPTED
    await _expire_other_offers(session, quote.id, offer.id)

    business = await session.get(Business, offer.business_id)
    if business is not None:
        await notify_quote_accepted(
            session,
            owner_id=business.owner_id,
            quote_id=quote.id,
            business_name=business.name,
        )
    await session.commit()
    try:
        await quote_broker.clear_retry(quote.id)
    except Exception:  # noqa: BLE001
        pass
    await session.refresh(offer)
    return {"data": offer_payload(offer, business=business, include_business_phone=True)}
