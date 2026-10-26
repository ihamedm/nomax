from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_db
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.services.business_search import (
    BusinessHit,
    BusinessSearchParams,
    decode_cursor,
    search_businesses,
)

router = APIRouter(prefix="/businesses", tags=["businesses"])

SortMode = Literal["nearest", "top", "newest", "urgent"]


def _category_payload(category: Category | None) -> dict | None:
    if category is None:
        return None
    return {
        "id": category.id,
        "slug": category.slug,
        "name": category.name,
        "icon": category.icon,
    }


def _subcategory_payload(subcategory: Subcategory | None) -> dict | None:
    if subcategory is None:
        return None
    return {
        "id": subcategory.id,
        "slug": subcategory.slug,
        "name": subcategory.name,
        "icon": subcategory.icon,
    }


def _business_payload(hit: BusinessHit, *, detail: bool = False) -> dict:
    business = hit.business
    payload = {
        "id": str(business.id),
        "slug": business.slug,
        "name": business.name,
        "short_description": business.short_description,
        "address": business.address,
        "phone_business": business.phone_business,
        "category": _category_payload(business.category),
        "subcategory": _subcategory_payload(business.subcategory),
        "geo": (
            {"lat": business.geo_lat, "lng": business.geo_lng}
            if business.geo_lat is not None and business.geo_lng is not None
            else None
        ),
        "distance_m": round(hit.distance_m) if hit.distance_m is not None else None,
        "rating_avg": round(business.rating_avg or 0, 2),
        "rating_count": business.rating_count or 0,
        "is_24h": business.is_24h,
        "is_verified": business.is_verified,
        "profile_image_url": business.profile_image_url,
        "created_at": business.created_at.isoformat() if business.created_at else None,
    }
    if detail:
        payload.update(
            {
                "description": business.description,
                "instagram": business.instagram,
                # Reviews are added in Phase 4.
                "reviews": [],
            }
        )
    return payload


@router.get("")
async def list_businesses(
    q: str | None = Query(None, max_length=120),
    cat: str | None = Query(None, max_length=80),
    subcat: str | None = Query(None, max_length=80),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    radius_km: float = Query(10, gt=0, le=50),
    sort: SortMode = "nearest",
    cursor: str | None = Query(None, max_length=200),
    limit: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if (lat is None) != (lng is None):
        raise AppError(
            "validation_error",
            "lat_and_lng_required_together",
            422,
            {"lat": lat, "lng": lng},
        )

    page = await search_businesses(
        session,
        BusinessSearchParams(
            q=q,
            category_slug=cat,
            subcategory_slug=subcat,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            sort=sort,
            limit=limit,
            offset=decode_cursor(cursor),
        ),
    )
    return {
        "data": {"items": [_business_payload(hit) for hit in page.hits]},
        "meta": {"has_more": page.has_more, "next_cursor": page.next_cursor},
    }


@router.get("/{slug}")
async def get_business(slug: str, session: AsyncSession = Depends(get_db)) -> dict:
    statement = (
        sa.select(Business)
        .join(Category, Business.category_id == Category.id)
        .outerjoin(Subcategory, Business.subcategory_id == Subcategory.id)
        .where(
            Business.slug == slug,
            Business.status == BusinessStatus.APPROVED,
            Business.deleted_at.is_(None),
            Category.deleted_at.is_(None),
        )
    )
    business = (await session.execute(statement)).scalars().first()
    if business is None:
        raise AppError("not_found", "business_not_found", 404, {"slug": slug})
    return {"data": _business_payload(BusinessHit(business=business), detail=True)}
