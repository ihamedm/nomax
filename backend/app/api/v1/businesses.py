import re
import uuid
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.deps import get_current_user, get_optional_user, require_permissions
from app.core.errors import AppError
from app.core.permissions import has_permission
from app.db.session import get_db
from app.models.bookmark import Bookmark
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
from app.services.inapp_notifications import (
    notify_business_approved,
    notify_business_rejected,
)

router = APIRouter(prefix="/businesses", tags=["businesses"])
me_router = APIRouter(tags=["owner"])
uploads_router = APIRouter(tags=["uploads"])

SortMode = Literal["nearest", "top", "newest", "urgent", "visited"]


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
        "view_count": business.view_count or 0,
        "is_24h": business.is_24h,
        "is_verified": business.is_verified,
        "status": (
            business.status.value if hasattr(business.status, "value") else str(business.status)
        ),
        "rejection_reason": business.rejection_reason,
        "profile_image_url": business.profile_image_url,
        "created_at": business.created_at.isoformat() if business.created_at else None,
    }
    if detail:
        payload.update(
            {
                "description": business.description,
                "instagram": business.instagram,
                "reviews": [],
            }
        )
    return payload


async def _recalculate_business_rating(session: AsyncSession, business_id: uuid.UUID) -> None:
    """Rating is calculated only from approved, public reviews."""
    await session.flush()
    business = await session.get(Business, business_id)
    if business is None:
        return
    avg, count = (
        await session.execute(
            sa.select(sa.func.avg(Review.rating), sa.func.count(Review.id)).where(
                Review.business_id == business_id,
                Review.status == "approved",
                Review.is_private.is_(False),
                Review.deleted_at.is_(None),
            )
        )
    ).one()
    business.rating_avg = float(avg or 0)
    business.rating_count = int(count or 0)


def _review_payload(review: Review) -> dict:
    return {
        "id": str(review.id),
        "rating": review.rating,
        "text": review.text,
        "author_name": review.author_name,
        "reply": review.reply,
        "replied_at": review.replied_at.isoformat() if review.replied_at else None,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


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


MAX_TAGS = 30
MAX_TAG_LENGTH = 60


def _clean_tags(raw: object) -> list[str]:
    """Validate and de-duplicate the tag names sent by the wizard.

    Standard tags (from the chosen subcategory) and owner-supplied tags share
    the same table, so the API caps the combined list; the UI is responsible
    for limiting custom tags to four.
    """

    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AppError("validation_error", "tags_must_be_a_list", 422)

    names: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name:
            continue
        if len(name) > MAX_TAG_LENGTH:
            raise AppError("validation_error", "tag_too_long", 422)
        if name not in names:
            names.append(name)

    if len(names) > MAX_TAGS:
        raise AppError("validation_error", "too_many_tags", 422)
    return names


async def _assign_tags(
    session: AsyncSession,
    business_id: uuid.UUID,
    names: list[str],
    *,
    standard_names: set[str] | None = None,
) -> None:
    """Replace a business' tags, auto-approving the catalog's standard tags."""

    from app.models.tag import BusinessTag, Tag

    standard_names = standard_names or set()
    await session.execute(sa.delete(BusinessTag).where(BusinessTag.business_id == business_id))
    for name in names:
        tag = (await session.execute(sa.select(Tag).where(Tag.name == name))).scalars().first()
        if tag is None:
            is_standard = name in standard_names
            tag = Tag(
                name=name,
                is_custom=not is_standard,
                status="approved" if is_standard else "pending",
            )
            session.add(tag)
            await session.flush()
        elif name in standard_names and (tag.is_custom or tag.status != "approved"):
            # A catalog tag may already exist as a pending custom tag.
            tag.is_custom = False
            tag.status = "approved"
        session.add(BusinessTag(business_id=business_id, tag_id=tag.id))


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
    if len(name) > 160:
        raise AppError("validation_error", "name_too_long", 422)

    active_count = int(
        (
            await session.execute(
                sa.select(sa.func.count(Business.id)).where(
                    Business.owner_id == user.id, Business.deleted_at.is_(None)
                )
            )
        ).scalar()
        or 0
    )
    if active_count >= settings.MAX_BUSINESSES_PER_OWNER:
        raise AppError(
            "business_limit_reached",
            "business_limit_reached",
            409,
            {"limit": settings.MAX_BUSINESSES_PER_OWNER},
        )

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
    subcategory: Subcategory | None = None
    if subcategory_id is not None:
        subcategory = await session.get(Subcategory, subcategory_id)
        if subcategory is None:
            raise AppError("not_found", "subcategory_not_found", 404)
        if subcategory.category_id != category.id:
            raise AppError("validation_error", "subcategory_category_mismatch", 422)

    geo_lat = payload.get("geo_lat")
    geo_lng = payload.get("geo_lng")
    if (geo_lat is None) != (geo_lng is None):
        raise AppError("validation_error", "lat_and_lng_required_together", 422)
    if geo_lat is not None:
        try:
            geo_lat = float(geo_lat)
            geo_lng = float(geo_lng)
        except (TypeError, ValueError):
            raise AppError("validation_error", "invalid_coordinates", 422)
        if not (-90 <= geo_lat <= 90 and -180 <= geo_lng <= 180):
            raise AppError("validation_error", "invalid_coordinates", 422)

    phone_business = (payload.get("phone_business") or "").strip() or None
    if phone_business and not re.fullmatch(r"0\d{10}", phone_business):
        raise AppError("validation_error", "invalid_phone_business", 422)

    instagram = (payload.get("instagram") or "").strip() or None
    if instagram and len(instagram) > 100:
        raise AppError("validation_error", "instagram_too_long", 422)

    profile_image_url = (payload.get("profile_image_url") or "").strip() or None
    if profile_image_url and len(profile_image_url) > 255:
        raise AppError("validation_error", "profile_image_url_too_long", 422)

    tags = _clean_tags(payload.get("tags"))

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or str(uuid.uuid4())[:8]
    slug = f"{slug}-{str(uuid.uuid4())[:6]}"

    business = Business(
        owner_id=user.id,
        category_id=category_id,
        subcategory_id=subcategory_id,
        name=name,
        slug=slug,
        short_description=(payload.get("short_description") or "").strip()[:120],
        description=payload.get("description"),
        phone_business=phone_business,
        address=(payload.get("address") or "").strip()[:255],
        geo_lat=geo_lat,
        geo_lng=geo_lng,
        instagram=instagram,
        is_24h=bool(payload.get("is_24h", False)),
        profile_image_url=profile_image_url,
    )
    session.add(business)
    await session.flush()

    if tags:
        await _assign_tags(
            session,
            business.id,
            tags,
            standard_names=set(subcategory.standard_tags or []) if subcategory else set(),
        )

    if user.role == UserRole.CUSTOMER:
        user.role = UserRole.OWNER
        await session.flush()

    await session.commit()
    await session.refresh(business)
    return {"data": _business_payload(BusinessHit(business=business), detail=True)}


@me_router.get("/me/businesses/{business_id}/tags")
async def get_business_tags(
    business_id: str,
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
    rows = (
        await session.execute(
            sa.select(Tag.name)
            .join(BusinessTag, BusinessTag.tag_id == Tag.id)
            .where(BusinessTag.business_id == bid)
            .order_by(Tag.name)
        )
    ).scalars().all()
    return {"data": {"tags": list(rows)}}


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
    before = {
        "status": business.status.value if hasattr(business.status, "value") else str(business.status),
        "rejection_reason": business.rejection_reason,
    }
    reason = (payload.get("rejection_reason") or "").strip() or None
    if status == "rejected" and not reason:
        raise AppError("rejection_reason_required", "rejection_reason_required", 422)
    if status != "rejected":
        reason = None
    business.status = BusinessStatus(status)
    business.rejection_reason = reason
    status_changed = before["status"] != status
    if status_changed and status == "rejected":
        await notify_business_rejected(
            session,
            owner_id=business.owner_id,
            business_id=business.id,
            business_slug=business.slug,
            business_name=business.name,
            reason=reason,
        )
    elif status_changed and status == "approved":
        await notify_business_approved(
            session,
            owner_id=business.owner_id,
            business_id=business.id,
            business_slug=business.slug,
            business_name=business.name,
        )
    session.add(
        AuditLog(
            actor_id=user.id,
            action="business.status_change",
            entity_type="business",
            entity_id=str(business.id),
            before=before,
            after={"status": status, "rejection_reason": reason},
        )
    )
    await session.commit()
    await session.refresh(business)
    return {"data": _business_payload(BusinessHit(business=business), detail=True)}


MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@uploads_router.post("/uploads/image")
@uploads_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    crop: str = Form("square"),
    filter: str = Form("none"),
    anchor: str = Form("center"),
    user=Depends(get_current_user),
) -> dict:
    """Process a user-uploaded business image and store its named crops.

    Admin file-manager uploads use ``/admin/files/upload`` and stay untouched.
    """
    if not (file.content_type or "").startswith("image/"):
        raise AppError("validation_error", "image_required", 422)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError("validation_error", "image_too_large", 413)

    from app.services.image_processor import (
        ANCHORS,
        CROP_PRESETS,
        FILTERS,
        InvalidImage,
        process_image,
    )
    from app.services.storage import save_image_bundle, user_upload_prefix

    if crop not in (*CROP_PRESETS, "original"):
        raise AppError("invalid_crop", "invalid_crop", 422)
    if filter not in FILTERS:
        raise AppError("invalid_filter", "invalid_filter", 422)
    if anchor not in ANCHORS:
        raise AppError("invalid_anchor", "invalid_anchor", 422)

    try:
        processed = await run_in_threadpool(
            process_image, data, crop=crop, filter=filter, anchor=anchor
        )
    except InvalidImage as exc:
        code = str(exc) or "invalid_image"
        raise AppError("invalid_image", code, 422)

    # The main image and the variant for its crop are byte-identical; store
    # them once and point the variant at the main object.
    saved = await save_image_bundle(
        processed.main.data,
        {
            name: variant.data
            for name, variant in processed.variants.items()
            if name != crop
        },
        prefix=user_upload_prefix("businesses", user.id),
    )
    variants: dict[str, dict] = {}
    for name, variant in processed.variants.items():
        if name == crop:
            stored = {
                "url": saved["url"],
                "key": saved["key"],
                "size": processed.main.size,
            }
        else:
            stored = saved["variants"][name]
        variants[name] = {
            "url": stored["url"],
            "key": stored["key"],
            "width": variant.width,
            "height": variant.height,
            "size": variant.size,
        }

    return {
        "data": {
            "url": saved["url"],
            "key": saved["key"],
            "width": processed.main.width,
            "height": processed.main.height,
            "size": processed.main.size,
            "crop": crop,
            "filter": filter,
            "anchor": anchor,
            "variants": variants,
        }
    }


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
    if business.owner_id == user.id:
        raise AppError("cannot_review_own_business", "cannot_review_own_business", 403)
    existing = (
        await session.execute(
            sa.select(Review.id).where(
                Review.business_id == business.id,
                Review.user_id == user.id,
                Review.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if existing is not None:
        raise AppError("review_already_exists", "review_already_exists", 409)

    rating = int(payload.get("rating", 0))
    if rating < 1 or rating > 5:
        raise AppError("validation_error", "invalid_rating", 422)
    text = (payload.get("text") or "").strip() or None
    if text and len(text) > 300:
        raise AppError("review_too_long", "review_too_long", 422)
    is_private = bool(payload.get("is_private"))
    review = Review(
        business_id=business.id,
        user_id=user.id,
        rating=rating,
        text=text,
        author_name=user.full_name or "کاربر نومکس",
        is_private=is_private,
        status="private" if is_private else "pending",
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return {
        "data": {
            "id": str(review.id),
            "status": review.status,
            "is_private": review.is_private,
        }
    }

@router.patch("/reviews/{review_id}/status")
async def moderate_review(
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
    if review is None:
        raise AppError("not_found", "review_not_found", 404)
    if review.is_private:
        raise AppError(
            "private_review_not_moderatable", "private_review_not_moderatable", 422
        )
    business = await session.get(Business, review.business_id)
    if business is None or business.deleted_at is not None:
        raise AppError("not_found", "business_not_found", 404)
    if business.owner_id != user.id and not has_permission(user, "review.moderate"):
        raise AppError("forbidden", "review_moderation_forbidden", 403)
    status = payload.get("status")
    if status not in ("approved", "rejected", "pending"):
        raise AppError("validation_error", "invalid_status", 422)
    review.status = status
    # Approval/rejection changes the public aggregate immediately.
    await _recalculate_business_rating(session, review.business_id)
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

    new_category_id = payload.get("category_id", business.category_id)
    category = await session.get(Category, new_category_id)
    if category is None or category.deleted_at is not None:
        raise AppError("not_found", "category_not_found", 404)

    if "subcategory_id" in payload:
        new_subcategory_id = payload["subcategory_id"]
    elif "category_id" in payload:
        new_subcategory_id = None
    else:
        new_subcategory_id = business.subcategory_id

    subcategory: Subcategory | None = None
    if new_subcategory_id is not None:
        subcategory = await session.get(Subcategory, new_subcategory_id)
        if subcategory is None:
            raise AppError("not_found", "subcategory_not_found", 404)
        if subcategory.category_id != category.id:
            raise AppError("validation_error", "subcategory_category_mismatch", 422)

    name = business.name
    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            raise AppError("validation_error", "name_required", 422)
        if len(name) > 160:
            raise AppError("validation_error", "name_too_long", 422)

    address = business.address
    if "address" in payload:
        address = (payload.get("address") or "").strip()[:255]

    geo_lat = payload.get("geo_lat", business.geo_lat)
    geo_lng = payload.get("geo_lng", business.geo_lng)
    if (geo_lat is None) != (geo_lng is None):
        raise AppError("validation_error", "lat_and_lng_required_together", 422)
    if geo_lat is not None:
        try:
            geo_lat = float(geo_lat)
            geo_lng = float(geo_lng)
        except (TypeError, ValueError):
            raise AppError("validation_error", "invalid_coordinates", 422)
        if not (-90 <= geo_lat <= 90 and -180 <= geo_lng <= 180):
            raise AppError("validation_error", "invalid_coordinates", 422)

    phone_business = business.phone_business
    if "phone_business" in payload:
        phone_business = (payload.get("phone_business") or "").strip() or None
        if phone_business and not re.fullmatch(r"0\d{10}", phone_business):
            raise AppError("validation_error", "invalid_phone_business", 422)

    instagram = business.instagram
    if "instagram" in payload:
        instagram = (payload.get("instagram") or "").strip() or None
        if instagram and len(instagram) > 100:
            raise AppError("validation_error", "instagram_too_long", 422)

    profile_image_url = business.profile_image_url
    if "profile_image_url" in payload:
        profile_image_url = (payload.get("profile_image_url") or "").strip() or None
        if profile_image_url and len(profile_image_url) > 255:
            raise AppError("validation_error", "profile_image_url_too_long", 422)

    tags = _clean_tags(payload.get("tags")) if "tags" in payload else None

    # Only actual critical edits send the business back to moderation.
    critical_changed = (
        name != business.name
        or address != business.address
        or category.id != business.category_id
        or new_subcategory_id != business.subcategory_id
    )

    business.name = name
    business.address = address
    business.category_id = category.id
    business.subcategory_id = new_subcategory_id
    business.geo_lat = geo_lat
    business.geo_lng = geo_lng
    business.phone_business = phone_business
    business.instagram = instagram
    business.profile_image_url = profile_image_url
    if "short_description" in payload:
        business.short_description = (payload.get("short_description") or "").strip()[:120]
    if "description" in payload:
        business.description = payload.get("description")
    if "is_24h" in payload:
        business.is_24h = bool(payload["is_24h"])

    if tags is not None:
        await _assign_tags(
            session,
            business.id,
            tags,
            standard_names=set(subcategory.standard_tags or []) if subcategory else set(),
        )

    if critical_changed or (
        business.status == BusinessStatus.REJECTED and user.id == business.owner_id
    ):
        # Any owner edit on a rejected business is a resubmission for review.
        business.status = BusinessStatus.PENDING
        business.rejection_reason = None

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


@me_router.get("/me/businesses")
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
    limit = settings.MAX_BUSINESSES_PER_OWNER
    return {
        "data": {
            "items": [_business_payload(BusinessHit(business=b)) for b in rows],
            "limit": limit,
            "can_create": len(rows) < limit,
        }
    }


@me_router.get("/me/businesses/{business_id}")
async def my_business(
    business_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.tag import BusinessTag, Tag

    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None or business.deleted_at is not None or business.owner_id != user.id:
        raise AppError("not_found", "business_not_found", 404)

    payload = _business_payload(BusinessHit(business=business), detail=True)
    if payload["subcategory"] is not None and business.subcategory is not None:
        payload["subcategory"]["standard_tags"] = list(business.subcategory.standard_tags or [])

    tags = (
        await session.execute(
            sa.select(Tag.name)
            .join(BusinessTag, BusinessTag.tag_id == Tag.id)
            .where(BusinessTag.business_id == business.id)
            .order_by(Tag.name)
        )
    ).scalars().all()
    payload["tags"] = list(tags)
    return {"data": payload}


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
    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None or business.owner_id != user.id:
        raise AppError("not_found", "business_not_found", 404)
    names = _clean_tags(payload.get("tags"))
    standard_names: set[str] = set()
    if business.subcategory_id is not None:
        subcategory = await session.get(Subcategory, business.subcategory_id)
        if subcategory is not None:
            standard_names = set(subcategory.standard_tags or [])
    await _assign_tags(session, bid, names, standard_names=standard_names)
    await session.commit()
    return {"data": {"tags": names}}


@me_router.get("/me/businesses/{business_id}/analytics")
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
                Review.business_id == bid,
                Review.status == "approved",
                Review.is_private.is_(False),
                Review.deleted_at.is_(None),
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
async def get_business(
    slug: str,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict:
    statement = (
        sa.select(Business)
        .join(Category, Business.category_id == Category.id)
        .outerjoin(Subcategory, Business.subcategory_id == Subcategory.id)
        .where(
            Business.slug == slug,
            Business.deleted_at.is_(None),
            Category.deleted_at.is_(None),
        )
    )
    business = (await session.execute(statement)).scalars().first()
    if business is None:
        raise AppError("not_found", "business_not_found", 404, {"slug": slug})
    is_owner = user is not None and business.owner_id == user.id
    is_admin = user is not None and user.role in (UserRole.ADMIN, UserRole.SUPERADMIN)
    if business.status != BusinessStatus.APPROVED and not (is_owner or is_admin):
        # Pending/rejected businesses stay hidden from the public, but their
        # owner (and admins) must be able to open them to see the status.
        raise AppError("not_found", "business_not_found", 404, {"slug": slug})
    reviews = (
        await session.execute(
            sa.select(Review)
            .where(
                Review.business_id == business.id,
                Review.status == "approved",
                Review.is_private.is_(False),
                Review.deleted_at.is_(None),
            )
            .order_by(Review.created_at.desc())
        )
    ).scalars().all()
    if business.status == BusinessStatus.APPROVED:
        business.view_count = (business.view_count or 0) + 1
    data = _business_payload(BusinessHit(business=business), detail=True)
    data["is_owner"] = is_owner
    data["is_saved"] = False
    data["my_review"] = None
    if user is not None:
        saved = (
            await session.execute(
                sa.select(Bookmark.id).where(
                    Bookmark.user_id == user.id, Bookmark.business_id == business.id
                )
            )
        ).scalars().first()
        data["is_saved"] = saved is not None
        my_review = (
            await session.execute(
                sa.select(Review).where(
                    Review.business_id == business.id,
                    Review.user_id == user.id,
                    Review.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if my_review is not None:
            data["my_review"] = {
                "id": str(my_review.id),
                "status": my_review.status,
                "is_private": my_review.is_private,
            }
    data["reviews"] = [_review_payload(review) for review in reviews]
    await session.commit()
    return {"data": data}
