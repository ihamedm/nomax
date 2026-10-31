import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.core.errors import AppError
from app.db.session import get_db
from app.models.admin import AuditLog
from app.models.analytics import QuoteDelivery, QuoteDispatchRun
from app.models.business import Business, BusinessStatus
from app.models.quote import Offer, QuoteRequest
from app.models.user import User
from app.services import quote_broker
from app.services.inapp_notifications import notify_quote_cancelled
from app.services.quote_dispatcher import dispatch_manual_businesses, retry_due_quote
from app.services.quote_service import (
    ACCEPTED,
    ACTIVE,
    CANCELLED,
    DECLINED,
    EXPIRED,
    PENDING,
    expire_stale_quotes,
    dispatch_summaries,
    offer_counts,
    offer_payload,
    offers_by_id,
    quote_payload,
)
from app.services.quote_dispatch_settings import get_quote_dispatch_config

router = APIRouter(prefix="/admin/quotes", tags=["admin-quotes"])

VALID_STATUSES = (ACTIVE, ACCEPTED, CANCELLED, EXPIRED)


async def _get_quote(session: AsyncSession, quote_id: str) -> QuoteRequest:
    try:
        qid = uuid.UUID(quote_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    quote = await session.get(QuoteRequest, qid)
    if quote is None or quote.deleted_at is not None:
        raise AppError("not_found", "quote_not_found", 404)
    return quote


@router.get("/stats")
async def quote_stats(
    actor: User = Depends(require_permissions("quote.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    await expire_stale_quotes(session)

    async def count(*conditions) -> int:
        return int(
            (
                await session.execute(
                    select(func.count(QuoteRequest.id)).where(
                        QuoteRequest.deleted_at.is_(None), *conditions
                    )
                )
            ).scalar()
            or 0
        )

    total = await count()
    accepted = await count(QuoteRequest.status == ACCEPTED)
    offers_total = int(
        (
            await session.execute(
                select(func.count(Offer.id)).where(Offer.deleted_at.is_(None))
            )
        ).scalar()
        or 0
    )
    pending_offers = int(
        (
            await session.execute(
                select(func.count(Offer.id)).where(
                    Offer.deleted_at.is_(None), Offer.status == PENDING
                )
            )
        ).scalar()
        or 0
    )
    return {
        "data": {
            "total": total,
            "active": await count(QuoteRequest.status == ACTIVE),
            "urgent_active": await count(
                QuoteRequest.status == ACTIVE, QuoteRequest.is_urgent.is_(True)
            ),
            "accepted": accepted,
            "cancelled": await count(QuoteRequest.status == CANCELLED),
            "expired": await count(QuoteRequest.status == EXPIRED),
            "offers_total": offers_total,
            "pending_offers": pending_offers,
            "acceptance_rate": round((accepted / total) * 100, 1) if total else 0,
        }
    }



async def _dispatch_detail(session: AsyncSession, quote: QuoteRequest) -> dict:
    config = await get_quote_dispatch_config(session)
    summaries = await dispatch_summaries(session, [quote], config)
    delivery_rows = (
        await session.execute(
            select(QuoteDelivery, Business, User)
            .join(Business, QuoteDelivery.business_id == Business.id)
            .join(User, Business.owner_id == User.id)
            .where(QuoteDelivery.request_id == quote.id)
            .order_by(QuoteDelivery.round, QuoteDelivery.sent_at)
        )
    ).all()
    offers = (
        await session.execute(
            select(Offer).where(
                Offer.request_id == quote.id, Offer.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    offer_by_business = {offer.business_id: offer for offer in offers}
    runs = (
        await session.execute(
            select(QuoteDispatchRun)
            .where(QuoteDispatchRun.request_id == quote.id)
            .order_by(QuoteDispatchRun.created_at.desc())
            .limit(30)
        )
    ).scalars().all()
    return {
        "summary": summaries.get(quote.id),
        "settings": config.model_dump(),
        "deliveries": [
            {
                "business": {
                    "id": str(business.id),
                    "name": business.name,
                    "slug": business.slug,
                    "is_verified": business.is_verified,
                    "is_24h": business.is_24h,
                    "category": business.category.name if business.category else None,
                },
                "owner": {
                    "id": str(owner.id),
                    "name": owner.full_name,
                    "phone": owner.phone,
                },
                "round": delivery.round,
                "source": delivery.source,
                "sent_at": delivery.sent_at.isoformat() if delivery.sent_at else None,
                "seen_at": delivery.seen_at.isoformat() if delivery.seen_at else None,
                "responded_at": (
                    delivery.responded_at.isoformat() if delivery.responded_at else None
                ),
                "offer_status": (
                    offer_by_business[delivery.business_id].status
                    if delivery.business_id in offer_by_business
                    else None
                ),
            }
            for delivery, business, owner in delivery_rows
        ],
        "runs": [
            {
                "id": str(run.id),
                "round": run.round,
                "trigger": run.trigger,
                "candidate_count": run.candidate_count,
                "delivered_count": run.delivered_count,
                "detail": run.detail or {},
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            for run in runs
        ],
    }


async def _schedule_next(quote: QuoteRequest) -> None:
    if quote.next_dispatch_at is None:
        return
    try:
        await quote_broker.schedule_retry(quote.id, quote.next_dispatch_at)
    except Exception:  # noqa: BLE001 - DB schedule remains authoritative
        pass


@router.get("/{quote_id}/dispatch")
async def quote_dispatch_detail(
    quote_id: str,
    actor: User = Depends(require_permissions("quote.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    quote = await _get_quote(session, quote_id)
    return {"data": await _dispatch_detail(session, quote)}


@router.post("/{quote_id}/assign")
async def assign_quote_businesses(
    quote_id: str,
    payload: dict,
    request: Request,
    actor: User = Depends(require_permissions("quote.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    quote = await _get_quote(session, quote_id)
    if quote.status != ACTIVE:
        raise AppError("conflict", "quote_not_active", 409)
    raw_ids = payload.get("business_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise AppError("validation_error", "business_ids_required", 422)
    if len(raw_ids) > 20:
        raise AppError("validation_error", "too_many_businesses", 422)
    try:
        business_ids = {uuid.UUID(str(value)) for value in raw_ids}
    except (ValueError, TypeError):
        raise AppError("validation_error", "invalid_business_id", 422)

    businesses = list(
        (
            await session.execute(
                select(Business).where(
                    Business.id.in_(business_ids),
                    Business.status == BusinessStatus.APPROVED,
                    Business.deleted_at.is_(None),
                    Business.owner_id != quote.customer_id,
                )
            )
        ).scalars().all()
    )
    if not businesses:
        raise AppError("validation_error", "no_assignable_business", 422)

    delivered = await dispatch_manual_businesses(
        session, quote, businesses, actor_id=actor.id
    )
    delivered_ids = {business.id for business in delivered}
    skipped = [str(business_id) for business_id in business_ids - delivered_ids]
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="admin.quote.manual_dispatch",
            entity_type="quote",
            entity_id=str(quote.id),
            before=None,
            after={
                "business_ids": [str(business.id) for business in delivered],
                "skipped": skipped,
            },
            ip=request.client.host if request.client else None,
        )
    )
    await session.commit()
    await _schedule_next(quote)
    detail = await _dispatch_detail(session, quote)
    detail["assigned"] = [
        {"id": str(business.id), "name": business.name} for business in delivered
    ]
    detail["skipped"] = skipped
    return {"data": detail}


@router.post("/{quote_id}/dispatch-now")
async def dispatch_quote_now(
    quote_id: str,
    request: Request,
    actor: User = Depends(require_permissions("quote.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    quote = await _get_quote(session, quote_id)
    if quote.status != ACTIVE:
        raise AppError("conflict", "quote_not_active", 409)
    delivered = await retry_due_quote(
        session, quote, datetime.now(timezone.utc), force=True
    )
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="admin.quote.force_dispatch",
            entity_type="quote",
            entity_id=str(quote.id),
            before=None,
            after={"business_ids": [str(business.id) for business in delivered]},
            ip=request.client.host if request.client else None,
        )
    )
    await session.commit()
    await _schedule_next(quote)
    detail = await _dispatch_detail(session, quote)
    detail["dispatched"] = [
        {"id": str(business.id), "name": business.name} for business in delivered
    ]
    return {"data": detail}


@router.get("")
async def list_quotes(
    status: Optional[str] = None,
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
    actor: User = Depends(require_permissions("quote.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    await expire_stale_quotes(session)
    page = max(1, page)
    per_page = min(100, max(1, per_page))

    conditions = [QuoteRequest.deleted_at.is_(None)]
    if status:
        if status not in VALID_STATUSES:
            raise AppError("validation_error", "invalid_status", 422)
        conditions.append(QuoteRequest.status == status)
    if category_id:
        conditions.append(QuoteRequest.category_id == category_id)
    if q:
        term = f"%{q.strip()}%"
        conditions.append(
            or_(
                QuoteRequest.title.ilike(term),
                QuoteRequest.description.ilike(term),
                QuoteRequest.address.ilike(term),
                User.full_name.ilike(term),
                User.phone.ilike(term),
            )
        )

    total = int(
        (
            await session.execute(
                select(func.count(QuoteRequest.id))
                .select_from(QuoteRequest)
                .join(User, QuoteRequest.customer_id == User.id)
                .where(*conditions)
            )
        ).scalar()
        or 0
    )
    rows = (
        await session.execute(
            select(QuoteRequest)
            .join(User, QuoteRequest.customer_id == User.id)
            .where(*conditions)
            .order_by(QuoteRequest.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).scalars().all()

    counts = await offer_counts(session, [quote.id for quote in rows])
    accepted_ids = [quote.accepted_offer_id for quote in rows if quote.accepted_offer_id]
    accepted_offers = await offers_by_id(session, accepted_ids)
    business_ids = {offer.business_id for offer in accepted_offers.values()}
    businesses = {}
    if business_ids:
        businesses = {
            business.id: business
            for business in (
                await session.execute(select(Business).where(Business.id.in_(business_ids)))
            ).scalars().all()
        }

    items = []
    for quote in rows:
        accepted = accepted_offers.get(quote.accepted_offer_id)
        items.append(
            quote_payload(
                quote,
                offers_count=counts.get(quote.id, 0),
                accepted_offer=accepted,
                accepted_business=businesses.get(accepted.business_id) if accepted else None,
                customer=quote.customer,
                include_customer_phone=True,
            )
        )
    pages = max(1, (total + per_page - 1) // per_page)
    return {
        "data": {"items": items},
        "meta": {"page": page, "per_page": per_page, "total": total, "pages": pages},
    }


@router.get("/{quote_id}")
async def get_quote_detail(
    quote_id: str,
    actor: User = Depends(require_permissions("quote.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    quote = await _get_quote(session, quote_id)
    await expire_stale_quotes(session)
    await session.refresh(quote)

    offers = (
        await session.execute(
            select(Offer)
            .where(Offer.request_id == quote.id, Offer.deleted_at.is_(None))
            .order_by(Offer.created_at.desc())
        )
    ).scalars().all()
    accepted = next(
        (offer for offer in offers if offer.id == quote.accepted_offer_id), None
    )
    accepted_business = (
        await session.get(Business, accepted.business_id) if accepted else None
    )
    data = quote_payload(
        quote,
        offers_count=len([offer for offer in offers if offer.status != DECLINED]),
        accepted_offer=accepted,
        accepted_business=accepted_business,
        customer=quote.customer,
        include_customer_phone=True,
    )
    data["offers"] = [
        offer_payload(offer, include_business_phone=True) for offer in offers
    ]
    return {"data": data}


@router.post("/{quote_id}/cancel")
async def cancel_quote(
    quote_id: str,
    request: Request,
    actor: User = Depends(require_permissions("quote.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    quote = await _get_quote(session, quote_id)
    if quote.status != ACTIVE:
        raise AppError("conflict", "quote_not_cancellable", 409)

    pending = (
        await session.execute(
            select(Offer).where(
                Offer.request_id == quote.id,
                Offer.status == PENDING,
                Offer.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for offer in pending:
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
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="admin.quote.cancelled",
            entity_type="quote",
            entity_id=str(quote.id),
            before={"status": ACTIVE},
            after={"status": CANCELLED},
            ip=request.client.host if request.client else None,
        )
    )
    await session.commit()
    try:
        await quote_broker.clear_retry(quote.id)
    except Exception:  # noqa: BLE001
        pass
    await session.refresh(quote)
    counts = await offer_counts(session, [quote.id])
    return {"data": quote_payload(quote, offers_count=counts.get(quote.id, 0))}
