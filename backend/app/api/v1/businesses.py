import re
import uuid
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.errors import AppError
from app.db.session import get_db
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.admin import AuditLog
from app.models.review import Review
from app.models.user import User, UserRole
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


@router.post("")
async def create_business(
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if user.role not in (UserRole.OWNER, UserRole.ADMIN, UserRole.SUPERADMIN):
        # Allow any authenticated user to create; they become owner.
        pass

    name = (payload.get("name") or "").strip()
    if not name:
        raise AppError("validation_error", "name_required", 422)
    if user.national_id:
        # One business per national ID (proposal §2.4).
        existing = (
            await session.execute(
                sa.select(Business.id)
                .join(User, Business.owner_id == User.id)
                .where(User.national_id == user.national_id, Business.deleted_at.is_(None))
            )
        ).scalars().first()
        if existing is not None:
            raise AppError("conflict", "national_id_already_used", 409)
    category_id = payload.get("category_id")
    if category_id is None:
        raise AppError("validation_error", "category_id_required", 422)

    category = await session.get(Category, category_id)
    if category is None or category.deleted_at is not None:
        raise AppError("not_found", "category_not_found", 404)

    subcategory_id = payload.get("subcategory_id")
    if subcategory_id is not None:
        sub = await session.get(Subcategory, subcategory_id)
        if sub is None:
            raise AppError("not_found", "subcategory_not_found", 404)

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or str(uuid.uuid4())[:8]
    slug = f"{slug}-{str(uuid.uuid4())[:6]}"

    business = Business(
        owner_id=user.id,
        category_id=category_id,
        subcategory_id=subcategory_id,
        name=name,
        slug=slug,
        short_description=(payload.get("short_description") or "")[:120],
        description=payload.get("description"),
        phone_business=payload.get("phone_business"),
        address=payload.get("address") or "",
        geo_lat=payload.get("geo_lat"),
        geo_lng=payload.get("geo_lng"),
        instagram=payload.get("instagram"),
        is_24h=bool(payload.get("is_24h", False)),
    )
    session.add(business)
    await session.flush()

    if user.role == UserRole.CUSTOMER:
        user.role = UserRole.OWNER
        await session.flush()

    await session.commit()
    await session.refresh(business)
    return {"data": _business_payload(BusinessHit(business=business), detail=True)}


@router.patch("/{business_id}/status")
async def update_business_status(
    business_id: str,
    payload: dict,
    user: User = Depends(require_permissions("business.approve")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None:
        raise AppError("not_found", "business_not_found", 404)
    status = payload.get("status")
    if status not in ("approved", "rejected", "pending"):
        raise AppError("validation_error", "invalid_status", 422)
    before = {"status": business.status.value if hasattr(business.status, "value") else str(business.status)}
    business.status = BusinessStatus(status)
    business.rejection_reason = payload.get("rejection_reason")
    session.add(
        AuditLog(
            actor_id=user.id,
            action="business.status_change",
            entity_type="business",
            entity_id=str(business.id),
            before=before,
            after={"status": status, "rejection_reason": payload.get("rejection_reason")},
        )
    )
    await session.commit()
    await session.refresh(business)
    return {"data": _business_payload(BusinessHit(business=business), detail=True)}


MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.post("/uploads/image")
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
) -> dict:
    if not (file.content_type or "").startswith("image/"):
        raise AppError("validation_error", "image_required", 422)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError("validation_error", "image_too_large", 413)

    from app.services.image_processor import InvalidImage, compress_image
    from app.services.storage import save_upload

    try:
        compressed = compress_image(data)
    except InvalidImage:
        raise AppError("validation_error", "invalid_image", 422)
    url = save_upload(compressed, "image.jpg")
    return {"data": {"url": url}}


@router.post("/{slug}/reviews")
async def create_review(
    slug: str,
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = sa.select(Business).where(Business.slug == slug, Business.deleted_at.is_(None))
    business = (await session.execute(stmt)).scalars().first()
    if business is None:
        raise AppError("not_found", "business_not_found", 404)
    rating = int(payload.get("rating", 0))
    if rating < 1 or rating > 5:
        raise AppError("validation_error", "invalid_rating", 422)
    review = Review(business_id=business.id, user_id=user.id, rating=rating, text=payload.get("text"))
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return {"data": {"id": str(review.id), "status": review.status}}

@router.patch("/reviews/{review_id}/status")
async def moderate_review(
    review_id: str,
    payload: dict,
    user: User = Depends(require_permissions("review.moderate")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        rid = uuid.UUID(review_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    review = await session.get(Review, rid)
    if review is None:
        raise AppError("not_found", "review_not_found", 404)
    status = payload.get("status")
    if status not in ("approved", "rejected", "pending"):
        raise AppError("validation_error", "invalid_status", 422)
    review.status = status
    # aggregate rating if approved
    if status == "approved":
        business = await session.get(Business, review.business_id)
        if business:
            from sqlalchemy import func

            avg, cnt = (await session.execute(
                sa.select(func.avg(Review.rating), func.count(Review.id)).where(
                    Review.business_id == business.id, Review.status == "approved", Review.deleted_at.is_(None)
                )
            )).one()
            business.rating_avg = float(avg or 0)
            business.rating_count = int(cnt or 0)
    await session.commit()
    return {"data": {"id": str(review.id), "status": review.status}}

@router.post("/reviews/{review_id}/reply")
async def reply_to_review(
    review_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        rid = uuid.UUID(review_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    review = await session.get(Review, rid)
    if review is None or review.deleted_at is not None:
        raise AppError("not_found", "review_not_found", 404)
    business = await session.get(Business, review.business_id)
    if business is None or business.owner_id != user.id:
        raise AppError("forbidden", "not_business_owner", 403)
    reply = (payload.get("reply") or "").strip()
    if not reply or len(reply) > 250:
        raise AppError("validation_error", "invalid_reply", 422)
    from datetime import datetime, timezone

    review.reply = reply
    review.replied_at = datetime.now(timezone.utc)
    await session.commit()
    return {"data": {"id": str(review.id), "reply": review.reply}}


@router.patch("/{business_id}")
async def update_business(
    business_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None or business.deleted_at is not None:
        raise AppError("not_found", "business_not_found", 404)
    if business.owner_id != user.id and user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise AppError("forbidden", "not_business_owner", 403)
    editable = ("name", "short_description", "description", "phone_business", "address",
                "geo_lat", "geo_lng", "instagram", "is_24h")
    for field in editable:
        if field in payload:
            setattr(business, field, payload[field])
    # Critical edits go back to moderation.
    if "name" in payload or "address" in payload or "category_id" in payload:
        business.status = BusinessStatus.PENDING
    if "category_id" in payload:
        business.category_id = payload["category_id"]
    await session.commit()
    await session.refresh(business)
    return {"data": _business_payload(BusinessHit(business=business), detail=True)}


@router.delete("/{business_id}")
async def delete_business(
    business_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None or business.deleted_at is not None:
        raise AppError("not_found", "business_not_found", 404)
    if business.owner_id != user.id:
        raise AppError("forbidden", "not_business_owner", 403)
    from datetime import datetime, timezone

    business.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    return {"data": {"id": str(business.id), "deleted": True}}


@router.get("/me/businesses")
async def my_businesses(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await session.execute(
            sa.select(Business).where(
                Business.owner_id == user.id, Business.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    return {"data": {"items": [_business_payload(BusinessHit(business=b)) for b in rows]}}


@router.post("/{business_id}/license")
async def upsert_license(
    business_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.license import License

    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None or business.owner_id != user.id:
        raise AppError("not_found", "business_not_found", 404)
    if not payload.get("license_number"):
        raise AppError("validation_error", "license_number_required", 422)
    license_row = (
        await session.execute(
            sa.select(License).where(License.business_id == bid, License.deleted_at.is_(None))
        )
    ).scalars().first()
    if license_row is None:
        license_row = License(business_id=bid, license_number=payload["license_number"])
        session.add(license_row)
    license_row.license_number = payload["license_number"]
    license_row.image_url = payload.get("image_url") or license_row.image_url
    license_row.is_verified_by_admin = False
    business.is_verified = False
    await session.commit()
    return {"data": {"id": str(license_row.id), "verified": False}}


@router.post("/{business_id}/tags")
async def set_business_tags(
    business_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.tag import BusinessTag, Tag

    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None or business.owner_id != user.id:
        raise AppError("not_found", "business_not_found", 404)
    names = list(dict.fromkeys(n.strip() for n in payload.get("tags", []) if n.strip()))
    if len(names) > 3:
        raise AppError("validation_error", "max_three_custom_tags", 422)
    await session.execute(sa.delete(BusinessTag).where(BusinessTag.business_id == bid))
    for name in names:
        tag = (
            await session.execute(sa.select(Tag).where(Tag.name == name))
        ).scalars().first()
        if tag is None:
            tag = Tag(name=name, is_custom=True, status="pending")
            session.add(tag)
            await session.flush()
        session.add(BusinessTag(business_id=bid, tag_id=tag.id))
    await session.commit()
    return {"data": {"tags": names}}


@router.get("/me/businesses/{business_id}/analytics")
async def business_analytics(
    business_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None or business.owner_id != user.id:
        raise AppError("not_found", "business_not_found", 404)
    from app.models.review import Review

    review_count = int(
        (await session.execute(
            sa.select(sa.func.count(Review.id)).where(
                Review.business_id == bid, Review.status == "approved", Review.deleted_at.is_(None)
            )
        )).scalar() or 0
    )
    return {"data": {
        "business_id": str(bid),
        "rating_avg": round(business.rating_avg or 0, 2),
        "rating_count": business.rating_count,
        "approved_reviews": review_count,
        "is_verified": business.is_verified,
    }}


@router.get("/{business_id}/qr")
async def business_qr(business_id: str, session: AsyncSession = Depends(get_db)):
    import io

    import segno
    from fastapi import Response

    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None:
        raise AppError("not_found", "business_not_found", 404)
    buffer = io.BytesIO()
    segno.make(f"/businesses/{business.slug}").save(buffer, kind="svg", scale=4)
    return Response(content=buffer.getvalue(), media_type="image/svg+xml")


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
    reviews = (
        await session.execute(
            sa.select(Review)
            .where(
                Review.business_id == business.id,
                Review.status == "approved",
                Review.deleted_at.is_(None),
            )
            .order_by(Review.created_at.desc())
        )
    ).scalars().all()
    data = _business_payload(BusinessHit(business=business), detail=True)
    data["reviews"] = [
        {
            "id": str(r.id),
            "rating": r.rating,
            "text": r.text,
            "author_name": r.author_name,
            "reply": r.reply,
            "replied_at": r.replied_at.isoformat() if r.replied_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reviews
    ]
    return {"data": data}
