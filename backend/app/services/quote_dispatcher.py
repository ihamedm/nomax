"""Quote dispatch: candidate selection + owner notification.

Timing rule (proposal §5.1): normal requests only 06:00–21:00; urgent requests
outside that window go only to `is_24h` businesses. Radius is 10km when the
request has coordinates. Phone numbers are never included in the payload.
"""
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business, BusinessStatus
from app.models.notification import Notification
from app.models.quote import QuoteRequest

DISPATCH_RADIUS_KM = 10.0


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    import math

    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def dispatch_quote(
    session: AsyncSession, quote: QuoteRequest, now: datetime | None = None
) -> list[Business]:
    now = now or datetime.now(timezone.utc)
    daytime = 6 <= now.hour < 21

    stmt = sa.select(Business).where(
        Business.category_id == quote.category_id,
        Business.status == BusinessStatus.APPROVED,
        Business.deleted_at.is_(None),
    )
    if quote.subcategory_id:
        stmt = stmt.where(Business.subcategory_id == quote.subcategory_id)
    if not daytime:
        stmt = stmt.where(Business.is_24h.is_(True))

    candidates = (await session.execute(stmt)).scalars().all()

    targeted: list[Business] = []
    for business in candidates:
        if quote.geo_lat is not None and quote.geo_lng is not None:
            if business.geo_lat is None or business.geo_lng is None:
                continue
            if _haversine_km(quote.geo_lat, quote.geo_lng, business.geo_lat, business.geo_lng) > DISPATCH_RADIUS_KM:
                continue
        targeted.append(business)
        session.add(
            Notification(
                user_id=business.owner_id,
                title="درخواست جدید",
                body=f"{quote.title[:80]}",
            )
        )
    return targeted


def expiry_for(is_urgent: bool, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now + (timedelta(hours=2) if is_urgent else timedelta(hours=24))
