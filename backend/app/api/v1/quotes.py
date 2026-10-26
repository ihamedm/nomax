import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.business import Business
from app.models.quote import Offer, QuoteRequest
from app.models.user import User
from app.services.quote_dispatcher import dispatch_quote, expiry_for

router = APIRouter(tags=["quotes"])


def _serialize_quote(q: QuoteRequest, *, customer_phone: str | None = None) -> dict:
    data = {
        "id": str(q.id),
        "title": q.title,
        "description": q.description,
        "category_id": q.category_id,
        "subcategory_id": q.subcategory_id,
        "address": q.address,
        "neighborhood": q.neighborhood,
        "is_urgent": q.is_urgent,
        "status": q.status,
        "expires_at": q.expires_at.isoformat() if q.expires_at else None,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }
    if customer_phone is not None:
        data["customer_phone"] = customer_phone
    return data


def _serialize_offer(o: Offer) -> dict:
    return {
        "id": str(o.id),
        "request_id": str(o.request_id),
        "business_id": str(o.business_id),
        "price": float(o.price) if o.price is not None else None,
        "brand": o.brand,
        "message": o.message,
        "status": o.status,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


async def _get_quote(session: AsyncSession, quote_id: str, *, lock: bool = False) -> QuoteRequest:
    try:
        qid = uuid.UUID(quote_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    stmt = sa.select(QuoteRequest).where(QuoteRequest.id == qid)
    if lock:
        stmt = stmt.with_for_update()
    quote = (await session.execute(stmt)).scalars().first()
    if quote is None or quote.deleted_at is not None:
        raise AppError("not_found", "quote_not_found", 404)
    return quote


async def _expire_other_offers(session: AsyncSession, quote_id, accepted_offer_id) -> None:
    offers = (
        await session.execute(
            sa.select(Offer).where(
                Offer.request_id == quote_id,
                Offer.id != accepted_offer_id,
                Offer.status == "pending",
            )
        )
    ).scalars().all()
    for offer in offers:
        offer.status = "expired"


def _check_not_expired(quote: QuoteRequest) -> None:
    if quote.status != "active":
        raise AppError("conflict", "quote_not_active", 409)
    expires_at = quote.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        quote.status = "expired"
        raise AppError("conflict", "quote_expired", 409)


@router.post("/quotes/requests")
@router.post("/quotes")
async def create_quote(
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    title = (payload.get("title") or payload.get("item_description") or "").strip()
    address = (payload.get("address") or "").strip()
    if not title or payload.get("category_id") is None or not address:
        raise AppError("validation_error", "title_address_category_required", 422)

    existing = (
        await session.execute(
            sa.select(QuoteRequest).where(
                QuoteRequest.customer_id == user.id,
                QuoteRequest.status == "active",
                QuoteRequest.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if existing is not None:
        _check_not_expired(existing)
        raise AppError("conflict", "active_quote_exists", 409)

    is_urgent = bool(payload.get("is_urgent", False))
    quote = QuoteRequest(
        customer_id=user.id,
        category_id=payload["category_id"],
        subcategory_id=payload.get("subcategory_id"),
        title=title,
        description=payload.get("description"),
        address=address,
        neighborhood=payload.get("neighborhood"),
        geo_lat=payload.get("geo_lat"),
        geo_lng=payload.get("geo_lng"),
        is_urgent=is_urgent,
        expires_at=expiry_for(is_urgent),
    )
    session.add(quote)
    await session.flush()
    await dispatch_quote(session, quote)
    await session.commit()
    await session.refresh(quote)
    return {"data": _serialize_quote(quote)}


@router.get("/quotes/requests/mine")
async def my_quotes(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await session.execute(
            sa.select(QuoteRequest)
            .where(QuoteRequest.customer_id == user.id, QuoteRequest.deleted_at.is_(None))
            .order_by(QuoteRequest.created_at.desc())
        )
    ).scalars().all()
    return {"data": {"items": [_serialize_quote(q) for q in rows]}}


@router.get("/quotes/requests/incoming")
async def incoming_quotes(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    business_ids = (
        await session.execute(
            sa.select(Business.id).where(Business.owner_id == user.id, Business.deleted_at.is_(None))
        )
    ).scalars().all()
    if not business_ids:
        return {"data": {"items": []}}
    rows = (
        await session.execute(
            sa.select(QuoteRequest)
            .where(
                QuoteRequest.status == "active",
                QuoteRequest.deleted_at.is_(None),
                QuoteRequest.category_id.in_(
                    sa.select(Business.category_id).where(Business.id.in_(business_ids))
                ),
            )
            .order_by(QuoteRequest.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    # Owner-facing payload must never include the customer phone.
    return {"data": {"items": [_serialize_quote(q) for q in rows]}}


@router.post("/quotes/requests/{quote_id}/cancel")
async def cancel_quote(
    quote_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    quote = await _get_quote(session, quote_id)
    if quote.customer_id != user.id:
        raise AppError("forbidden", "not_quote_owner", 403)
    quote.status = "cancelled"
    await session.commit()
    return {"data": _serialize_quote(quote)}


@router.get("/quotes/{quote_id}")
async def get_quote(
    quote_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    quote = await _get_quote(session, quote_id)
    offers = (
        await session.execute(sa.select(Offer).where(Offer.request_id == quote.id))
    ).scalars().all()
    data = {**_serialize_quote(quote), "offers": [_serialize_offer(o) for o in offers]}
    # Phone is revealed to the accepted business only, after acceptance.
    if quote.phone_revealed_to is not None:
        owned = (
            await session.execute(
                sa.select(Business.id).where(
                    Business.id == quote.phone_revealed_to, Business.owner_id == user.id
                )
            )
        ).scalars().first()
        if owned is not None:
            customer = await session.get(User, quote.customer_id)
            data["customer_phone"] = customer.phone if customer else None
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
    if business.category_id != quote.category_id:
        raise AppError("validation_error", "business_category_mismatch", 422)

    offer = Offer(
        request_id=quote.id,
        business_id=business.id,
        price=payload.get("price"),
        brand=payload.get("brand"),
        message=payload.get("message") or payload.get("notes"),
    )
    session.add(offer)
    await session.commit()
    await session.refresh(offer)
    return {"data": _serialize_offer(offer)}


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
    if offer is None:
        raise AppError("not_found", "offer_not_found", 404)
    if quote_id and str(offer.request_id) != quote_id:
        raise AppError("not_found", "offer_not_found", 404)

    quote = await _get_quote(session, str(offer.request_id), lock=True)
    if quote.customer_id != user.id:
        raise AppError("forbidden", "not_quote_owner", 403)
    _check_not_expired(quote)

    quote.status = "accepted"
    quote.accepted_offer_id = offer.id
    quote.phone_revealed_to = offer.business_id
    offer.status = "accepted"
    await _expire_other_offers(session, quote.id, offer.id)
    await session.commit()
    return {"data": _serialize_offer(offer)}
