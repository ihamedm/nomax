import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core import security
from app.core.config import settings
from app.core.deps import (
    client_ip,
    get_current_user,
    get_optional_user,
    get_otp_service,
    get_redis,
    require_permissions,
)
from app.core.errors import AppError
from app.core.permissions import has_permission
from app.db.session import get_db
from app.models.bookmark import Bookmark
from app.models.business import Business, BusinessImage, BusinessStatus
from app.models.analytics import QuoteDelivery
from app.models.business_like import BusinessLike
from app.models.category import Category, Subcategory
from app.models.admin import AuditLog
from app.models.review import Review
from app.models.user import User, UserRole
from app.services.auth_service import ensure_not_blocked, issue_tokens, rate_limit
from app.services.otp_service import OtpService
from app.services.shahkar_service import verify_mobile_owner
from app.services.business_search import (
    BusinessHit,
    BusinessSearchParams,
    decode_cursor,
    search_businesses,
)
from app.services.slug import unique_business_slug
from app.services import map_cache
from app.services.inapp_notifications import (
    notify_business_approved,
    notify_business_rejected,
)
from app.services.search_analytics import log_search

logger = logging.getLogger(__name__)

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


def _business_subcategories(business: Business) -> list[Subcategory]:
    """All picked subcategories, with the legacy single column as a fallback."""
    rows = [row for row in business.subcategories if row.deleted_at is None]
    if not rows and business.subcategory is not None:
        rows = [business.subcategory]
    return rows


async def _resolve_subcategories(
    session: AsyncSession,
    category_id: int,
    payload: dict,
) -> list[Subcategory] | None:
    """Read ``subcategory_ids`` (or the legacy single id) from a payload.

    Returns ``None`` when the payload does not mention subcategories, so an
    update can leave the current selection untouched.
    """
    if "subcategory_ids" in payload:
        raw = payload.get("subcategory_ids") or []
    elif "subcategory_id" in payload:
        single = payload.get("subcategory_id")
        raw = [] if single is None else [single]
    else:
        return None
    if not isinstance(raw, list):
        raise AppError("validation_error", "invalid_subcategory_ids", 422)

    ids: list[int] = []
    for value in raw:
        try:
            subcategory_id = int(value)
        except (TypeError, ValueError):
            raise AppError("validation_error", "invalid_subcategory_id", 422)
        if subcategory_id not in ids:
            ids.append(subcategory_id)
    if not ids:
        return []

    rows = (
        await session.execute(
            sa.select(Subcategory).where(
                Subcategory.id.in_(ids), Subcategory.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    if len(by_id) != len(ids):
        raise AppError("not_found", "subcategory_not_found", 404)
    ordered = [by_id[subcategory_id] for subcategory_id in ids]
    # Every subcategory must belong to the business's own parent category.
    for subcategory in ordered:
        if subcategory.category_id != category_id:
            raise AppError("validation_error", "subcategory_category_mismatch", 422)
    return ordered


def _apply_subcategories(business: Business, subcategories: list[Subcategory]) -> None:
    primary = subcategories[0] if subcategories else None
    business.subcategory_id = primary.id if primary is not None else None
    business.subcategory = primary
    business.subcategories = list(subcategories)


def _standard_tag_names(subcategories: list[Subcategory]) -> set[str]:
    names: set[str] = set()
    for subcategory in subcategories:
        names.update(subcategory.standard_tags or [])
    return names


def _visible_tag_names(subcategories: list[Subcategory]) -> set[str]:
    """Tags the wizard shows. An unset subset falls back to the first few."""
    names: set[str] = set()
    for subcategory in subcategories:
        tags = list(subcategory.standard_tags or [])
        visible = (
            subcategory.visible_tags
            if subcategory.visible_tags is not None
            else tags[: settings.MAX_VISIBLE_SUBCATEGORY_TAGS]
        )
        names.update(visible)
    return names


def _with_hidden_standard_tags(
    names: list[str], subcategories: list[Subcategory]
) -> list[str]:
    """Search-only tags are attached automatically; the owner never sees them.

    Existing businesses pick these up on their next edit; there is no backfill.
    """
    hidden = _standard_tag_names(subcategories) - _visible_tag_names(subcategories)
    return names + [name for name in hidden if name not in names]


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
        "subcategories": [
            _subcategory_payload(subcategory)
            for subcategory in _business_subcategories(business)
        ],
        "geo": (
            {"lat": business.geo_lat, "lng": business.geo_lng}
            if business.geo_lat is not None and business.geo_lng is not None
            else None
        ),
        "distance_m": round(hit.distance_m) if hit.distance_m is not None else None,
        "rating_avg": round(business.rating_avg or 0, 2),
        "rating_count": business.rating_count or 0,
        "like_count": business.like_count or 0,
        "view_count": business.view_count or 0,
        "is_24h": business.is_24h,
        "is_verified": business.is_verified,
        "is_license_verified": business.is_license_verified,
        "status": (
            business.status.value if hasattr(business.status, "value") else str(business.status)
        ),
        "rejection_reason": business.rejection_reason,
        "profile_image_url": business.profile_image_url,
        "avatar_url": business.avatar_url,
        "created_at": business.created_at.isoformat() if business.created_at else None,
        "updated_at": business.updated_at.isoformat() if business.updated_at else None,
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
    # No cap by default: `nearest` only changes the ordering. Operators/clients
    # that want a hard distance limit pass `radius_km` explicitly.
    radius_km: float | None = Query(None, gt=0, le=50),
    sort: SortMode = "nearest",
    cursor: str | None = Query(None, max_length=200),
    limit: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_optional_user),
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
    if cursor is None:
        try:
            await log_search(
                session,
                user=user,
                query=q,
                category_slug=cat,
                subcategory_slug=subcat,
                results_count=len(page.hits),
                first_business=page.hits[0].business if page.hits else None,
            )
            await session.flush()
        except Exception as exc:  # noqa: BLE001 - analytics must not break search
            logger.warning("search analytics write failed: %s", exc)
            await session.rollback()

    return {
        "data": {"items": [_business_payload(hit) for hit in page.hits]},
        "meta": {"has_more": page.has_more, "next_cursor": page.next_cursor},
    }


MAX_TAGS = 30
MAX_TAG_LENGTH = 60
MAX_IMAGE_URL_LENGTH = 255


def _clean_image_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url:
        return None
    if len(url) > MAX_IMAGE_URL_LENGTH:
        raise AppError("image_url_too_long", "image_url_too_long", 422)
    return url


def _clean_image_list(raw: object) -> list[dict]:
    """Validate the gallery payload while accepting legacy URL-only entries."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AppError("images_must_be_a_list", "images_must_be_a_list", 422)

    images: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            url = _clean_image_url(item)
            is_main = False
        elif isinstance(item, dict):
            url = _clean_image_url(item.get("url"))
            is_main = bool(item.get("is_main"))
        else:
            raise AppError("invalid_image", "invalid_image", 422)
        if not url or url in seen:
            continue
        if len(images) >= settings.MAX_BUSINESS_IMAGES:
            raise AppError(
                "too_many_images",
                "too_many_images",
                422,
                {"max": settings.MAX_BUSINESS_IMAGES},
            )
        seen.add(url)
        images.append({"url": url, "is_main": is_main})

    return images


def _resolve_business_images(payload: dict) -> tuple[list[dict], str | None]:
    """Return (gallery rows, main url) for a create/update payload.

    ``images`` is authoritative when supplied. ``profile_image_url`` remains
    accepted by older clients and always identifies the main image.
    """
    has_images = "images" in payload
    has_profile = "profile_image_url" in payload
    if not has_images and not has_profile:
        return [], None

    images = _clean_image_list(payload.get("images")) if has_images else []
    profile_url = _clean_image_url(payload.get("profile_image_url")) if has_profile else None

    if profile_url:
        for image in images:
            image["is_main"] = image["url"] == profile_url
        if not any(image["url"] == profile_url for image in images):
            if len(images) >= settings.MAX_BUSINESS_IMAGES:
                raise AppError(
                    "too_many_images",
                    "too_many_images",
                    422,
                    {"max": settings.MAX_BUSINESS_IMAGES},
                )
            images.insert(0, {"url": profile_url, "is_main": True})

    if images and not any(image["is_main"] for image in images):
        images[0]["is_main"] = True

    main_url = next((image["url"] for image in images if image["is_main"]), None)
    return images, main_url


async def _replace_business_images(
    session: AsyncSession, business_id: uuid.UUID, images: list[dict]
) -> None:
    await session.execute(sa.delete(BusinessImage).where(BusinessImage.business_id == business_id))
    for index, image in enumerate(images):
        session.add(
            BusinessImage(
                business_id=business_id,
                url=image["url"],
                is_main=bool(image["is_main"]),
                sort_order=index,
            )
        )
    await session.flush()


async def _business_images_payload(
    session: AsyncSession, business: Business
) -> list[dict]:
    rows = (
        (
            await session.execute(
                sa.select(BusinessImage)
                .where(BusinessImage.business_id == business.id)
                .order_by(BusinessImage.sort_order, BusinessImage.created_at)
            )
        )
        .scalars()
        .all()
    )
    if rows:
        return [
            {
                "id": str(image.id),
                "url": image.url,
                "is_main": image.is_main,
                "sort_order": image.sort_order,
            }
            for image in rows
        ]
    if business.profile_image_url:
        # Legacy rows created before the gallery migration.
        return [
            {
                "id": None,
                "url": business.profile_image_url,
                "is_main": True,
                "sort_order": 0,
            }
        ]
    return []


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

    subcategories = await _resolve_subcategories(session, category.id, payload) or []
    subcategory = subcategories[0] if subcategories else None

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

    images, profile_image_url = _resolve_business_images(payload)

    tags = _clean_tags(payload.get("tags"))

    slug = await unique_business_slug(session, name)

    business = Business(
        owner_id=user.id,
        category_id=category_id,
        subcategory_id=subcategory.id if subcategory is not None else None,
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
        avatar_url=_clean_image_url(payload.get("avatar_url")),
        subcategories=subcategories,
    )
    session.add(business)
    await session.flush()

    if images:
        await _replace_business_images(session, business.id, images)

    tag_names = _with_hidden_standard_tags(tags, subcategories)
    if tag_names:
        await _assign_tags(
            session,
            business.id,
            tag_names,
            standard_names=_standard_tag_names(subcategories),
        )

    if user.role == UserRole.CUSTOMER:
        user.role = UserRole.OWNER
        await session.flush()

    await session.commit()
    await session.refresh(business)
    data = _business_payload(BusinessHit(business=business), detail=True)
    data["images"] = await _business_images_payload(session, business)
    return {"data": data}


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
    if status not in ("approved", "rejected", "pending", "archived"):
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
    if status != "pending":
        business.pending_changes = None
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
            sa.select(Review).where(
                Review.business_id == business.id,
                Review.user_id == user.id,
            )
        )
    ).scalars().first()
    if existing is not None and existing.deleted_at is None:
        raise AppError("review_already_exists", "review_already_exists", 409)

    rating = int(payload.get("rating", 0))
    if rating < 1 or rating > 5:
        raise AppError("validation_error", "invalid_rating", 422)
    text = (payload.get("text") or "").strip() or None
    if text and len(text) > 300:
        raise AppError("review_too_long", "review_too_long", 422)
    is_private = bool(payload.get("is_private"))
    if existing is not None:
        # One row per user+business (unique constraint), so re-reviewing after
        # a moderation delete rewrites the soft-deleted row.
        review = existing
        review.rating = rating
        review.text = text
        review.author_name = user.full_name or "کاربر نومکس"
        review.is_private = is_private
        review.status = "private" if is_private else "pending"
        review.reply = None
        review.replied_at = None
        review.owner_seen_at = None
        review.deleted_at = None
    else:
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
    try:
        await session.commit()
    except IntegrityError:
        # Concurrent double-submit still hits the unique constraint.
        await session.rollback()
        raise AppError("review_already_exists", "review_already_exists", 409)
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
    is_moderator = has_permission(user, "review.moderate")
    status = payload.get("status")
    if status in ("awaiting_owner", "rejected", "pending"):
        # Admin acceptance only moves the review to the owner's inbox.
        if not is_moderator:
            raise AppError("forbidden", "review_moderation_forbidden", 403)
    elif status in ("approved", "declined"):
        # The owner only decides after the admin has accepted the review.
        if business.owner_id != user.id:
            raise AppError("forbidden", "review_moderation_forbidden", 403)
        if review.status != "awaiting_owner":
            raise AppError("review_not_ready", "review_not_ready", 409)
    else:
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

    if "subcategory_ids" in payload or "subcategory_id" in payload:
        new_subcategories = await _resolve_subcategories(session, category.id, payload)
    elif "category_id" in payload:
        new_subcategories = []
    else:
        new_subcategories = None
    selected_subcategories = (
        new_subcategories
        if new_subcategories is not None
        else _business_subcategories(business)
    )

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

    gallery_images, profile_image_url = _resolve_business_images(payload)
    images_changed = "images" in payload or "profile_image_url" in payload
    if not images_changed:
        profile_image_url = business.profile_image_url

    tags = _clean_tags(payload.get("tags")) if "tags" in payload else None
    if tags is not None:
        tags = _with_hidden_standard_tags(tags, selected_subcategories)

    short_description = (
        (payload.get("short_description") or "").strip()[:120]
        if "short_description" in payload
        else business.short_description
    )
    description = payload.get("description") if "description" in payload else business.description
    is_24h = bool(payload["is_24h"]) if "is_24h" in payload else business.is_24h
    avatar_url = (
        _clean_image_url(payload.get("avatar_url"))
        if "avatar_url" in payload
        else business.avatar_url
    )

    # Every changed field sends the business back to moderation, not just
    # name/address/category. ``changes`` maps field -> (before, after) and is
    # also stored as the admin's "what changed" note.
    was_approved = business.status == BusinessStatus.APPROVED
    was_reviewed = business.status in (BusinessStatus.APPROVED, BusinessStatus.REJECTED)
    current_geo = (
        {"lat": business.geo_lat, "lng": business.geo_lng}
        if business.geo_lat is not None and business.geo_lng is not None
        else None
    )
    next_geo = (
        {"lat": geo_lat, "lng": geo_lng}
        if geo_lat is not None and geo_lng is not None
        else None
    )
    current_category_name = business.category.name if business.category else None
    candidates = (
        ("name", business.name, name),
        ("short_description", business.short_description, short_description),
        ("description", business.description, description),
        ("phone_business", business.phone_business, phone_business),
        ("address", business.address, address),
        ("geo", current_geo, next_geo),
        ("instagram", business.instagram, instagram),
        ("is_24h", business.is_24h, is_24h),
        ("profile_image_url", business.profile_image_url, profile_image_url),
        ("avatar_url", business.avatar_url, avatar_url),
        ("category_id", current_category_name, category.name),
    )
    changes = {
        field: (before, after) for field, before, after in candidates if before != after
    }

    current_subcategories = _business_subcategories(business)
    current_subcategory_ids = {subcategory.id for subcategory in current_subcategories}
    next_subcategory_ids = (
        {subcategory.id for subcategory in new_subcategories}
        if new_subcategories is not None
        else current_subcategory_ids
    )
    if next_subcategory_ids != current_subcategory_ids:
        changes["subcategory_ids"] = (
            sorted(subcategory.name for subcategory in current_subcategories),
            sorted(subcategory.name for subcategory in selected_subcategories),
        )

    if images_changed:
        # Compare URLs in order; a main-image-only change is reported through
        # profile_image_url instead.
        current_images = [
            image["url"] for image in await _business_images_payload(session, business)
        ]
        next_images = [image["url"] for image in gallery_images]
        if current_images != next_images:
            changes["images"] = (current_images, next_images)

    if tags is not None:
        from app.models.tag import BusinessTag, Tag

        current_tags = set(
            (
                await session.execute(
                    sa.select(Tag.name)
                    .join(BusinessTag, BusinessTag.tag_id == Tag.id)
                    .where(BusinessTag.business_id == business.id)
                )
            ).scalars()
        )
        if current_tags != set(tags):
            changes["tags"] = (sorted(current_tags), sorted(tags))

    business.name = name
    business.address = address
    business.category_id = category.id
    if new_subcategories is not None:
        _apply_subcategories(business, new_subcategories)
    business.geo_lat = geo_lat
    business.geo_lng = geo_lng
    business.phone_business = phone_business
    business.instagram = instagram
    business.profile_image_url = profile_image_url
    business.avatar_url = avatar_url
    business.short_description = short_description
    business.description = description
    business.is_24h = is_24h

    if images_changed:
        await _replace_business_images(session, business.id, gallery_images)

    if tags is not None:
        await _assign_tags(
            session,
            business.id,
            tags,
            standard_names=_standard_tag_names(selected_subcategories),
        )

    if changes:
        if was_reviewed:
            business.pending_changes = {
                field: {"from": before, "to": after}
                for field, (before, after) in changes.items()
            }
        elif business.pending_changes is not None:
            # Another edit before approval: keep the original "from" values.
            merged = {
                field: dict(entry) for field, entry in business.pending_changes.items()
            }
            for field, (before, after) in changes.items():
                entry = merged.get(field)
                if entry is not None and entry.get("from") == after:
                    merged.pop(field)
                    continue
                if entry is None:
                    entry = {"from": before}
                    merged[field] = entry
                entry["to"] = after
            business.pending_changes = merged or None

    if changes or (
        business.status == BusinessStatus.REJECTED and user.id == business.owner_id
    ):
        # Any owner edit on a rejected business is a resubmission for review.
        business.status = BusinessStatus.PENDING
        business.rejection_reason = None

    # Explicit so gallery-only edits also move the public "last updated" time.
    business.updated_at = datetime.now(timezone.utc)
    if was_approved or business.status == BusinessStatus.APPROVED:
        # Name/address/coordinates may have changed under the map snapshot, or
        # an approved business just went back to moderation.
        await map_cache.enqueue_refresh(session)
    await session.commit()
    await session.refresh(business)
    data = _business_payload(BusinessHit(business=business), detail=True)
    data["images"] = await _business_images_payload(session, business)
    return {"data": data}


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


@me_router.post("/me/likes/{business_id}")
async def like_business(
    business_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if (
        business is None
        or business.deleted_at is not None
        or business.status != BusinessStatus.APPROVED
    ):
        raise AppError("not_found", "business_not_found", 404)
    existing = (
        await session.execute(
            sa.select(BusinessLike).where(
                BusinessLike.user_id == user.id, BusinessLike.business_id == business.id
            )
        )
    ).scalars().first()
    if existing is None:
        session.add(BusinessLike(user_id=user.id, business_id=business.id))
        # The counter is denormalized so list payloads need no extra query.
        # Pin updated_at: a like is not an edit.
        await session.execute(
            sa.update(Business)
            .where(Business.id == business.id)
            .values(
                like_count=sa.func.coalesce(Business.like_count, 0) + 1,
                updated_at=Business.updated_at,
            )
            .execution_options(synchronize_session=False)
        )
        await session.commit()
    count = int(
        (
            await session.execute(
                sa.select(sa.func.count(BusinessLike.id)).where(
                    BusinessLike.business_id == business.id
                )
            )
        ).scalar()
        or 0
    )
    return {"data": {"liked": True, "like_count": count}}


@me_router.delete("/me/likes/{business_id}")
async def unlike_business(
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
    existing = (
        await session.execute(
            sa.select(BusinessLike).where(
                BusinessLike.user_id == user.id, BusinessLike.business_id == business.id
            )
        )
    ).scalars().first()
    if existing is not None:
        await session.delete(existing)
        await session.execute(
            sa.update(Business)
            .where(Business.id == business.id)
            .values(
                like_count=sa.case(
                    (Business.like_count > 0, Business.like_count - 1), else_=0
                ),
                updated_at=Business.updated_at,
            )
            .execution_options(synchronize_session=False)
        )
        await session.commit()
    count = int(
        (
            await session.execute(
                sa.select(sa.func.count(BusinessLike.id)).where(
                    BusinessLike.business_id == business.id
                )
            )
        ).scalar()
        or 0
    )
    return {"data": {"liked": False, "like_count": count}}


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
            "max_images": settings.MAX_BUSINESS_IMAGES,
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
        payload["subcategory"]["visible_tags"] = business.subcategory.visible_tags
    by_id = {row.id: row for row in business.subcategories}
    for item in payload["subcategories"]:
        row = by_id.get(item["id"])
        if row is not None:
            item["standard_tags"] = list(row.standard_tags or [])
            item["visible_tags"] = row.visible_tags

    tags = (
        await session.execute(
            sa.select(Tag.name)
            .join(BusinessTag, BusinessTag.tag_id == Tag.id)
            .where(BusinessTag.business_id == business.id)
            .order_by(Tag.name)
        )
    ).scalars().all()
    payload["tags"] = list(tags)
    payload["images"] = await _business_images_payload(session, business)
    payload["max_images"] = settings.MAX_BUSINESS_IMAGES
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
    business.is_license_verified = False
    await session.commit()
    return {"data": {"id": str(license_row.id), "verified": False}}


_CLAIM_VERIFIED_PREFIX = "business:claim:{business_id}:{user_id}"
_CLAIM_VERIFIED_TTL_SECONDS = 900


async def _load_claim_target(
    session: AsyncSession, business_id: str
) -> tuple[Business, User]:
    """Business plus its owner, rejecting claims that cannot happen."""
    try:
        bid = uuid.UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None or business.deleted_at is not None:
        raise AppError("not_found", "business_not_found", 404)
    owner = await session.get(User, business.owner_id)
    if owner is None or owner.deleted_at is not None:
        raise AppError("not_found", "owner_not_found", 404)
    if owner.is_verified:
        raise AppError("owner_already_verified", "owner_already_verified", 409)
    return business, owner


@router.post("/{business_id}/claim/otp")
async def request_owner_claim_otp(
    business_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    otp_service: OtpService = Depends(get_otp_service),
) -> dict:
    """Send an OTP to the owner's phone to prove the caller holds that SIM."""
    _, owner = await _load_claim_target(session, business_id)
    ip = client_ip(request)
    await ensure_not_blocked(otp_service.redis, phone=owner.phone, ip=ip)
    code = await otp_service.issue(owner.phone, ip=ip, session=session, purpose="owner_claim")
    if code is None or settings.APP_ENV == "production":
        return {"data": {"status": "sent", "expires_in": settings.OTP_TTL_SECONDS}}
    return {
        "data": {"status": "issued", "dev_otp": code, "expires_in": settings.OTP_TTL_SECONDS}
    }


@router.post("/{business_id}/claim/otp/verify")
async def verify_owner_claim_otp(
    business_id: str,
    payload: dict,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    otp_service: OtpService = Depends(get_otp_service),
    redis=Depends(get_redis),
) -> dict:
    """Check the OTP and remember the caller may complete the owner profile."""
    business, owner = await _load_claim_target(session, business_id)
    await ensure_not_blocked(redis, phone=owner.phone, ip=client_ip(request))
    if not await otp_service.verify(owner.phone, str(payload.get("code") or "").strip()):
        raise AppError("otp_invalid", "invalid_or_expired_otp_code", 401)
    await redis.set(
        _CLAIM_VERIFIED_PREFIX.format(business_id=business.id, user_id=user.id),
        "1",
        ex=_CLAIM_VERIFIED_TTL_SECONDS,
    )
    return {"data": {"verified": True, "full_name": owner.full_name}}


@router.post("/{business_id}/claim/profile")
async def complete_owner_claim(
    business_id: str,
    payload: dict,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    """Set the real owner's credentials, then sign them in on the owner account."""
    business, owner = await _load_claim_target(session, business_id)
    marker = _CLAIM_VERIFIED_PREFIX.format(business_id=business.id, user_id=user.id)
    if not await redis.get(marker):
        raise AppError("owner_claim_not_verified", "owner_claim_not_verified", 403)

    full_name = str(payload.get("full_name") or "").strip()
    national_id = str(payload.get("national_id") or "").strip()
    password = str(payload.get("password") or "")
    if len(full_name) < 3 or len(full_name) > 120:
        raise AppError("validation_error", "full_name_required", 422)
    if not security.validate_iranian_national_id(national_id):
        raise AppError(
            "invalid_national_id", "invalid_national_id", 422, {"national_id": national_id}
        )
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise AppError(
            "password_too_short",
            "password_too_short",
            422,
            {"min_length": settings.PASSWORD_MIN_LENGTH},
        )
    if owner.national_id and owner.national_id != national_id:
        raise AppError("national_id_already_set", "national_id_already_set", 409)
    in_use = await session.execute(
        sa.select(User.id).where(User.national_id == national_id, User.id != owner.id)
    )
    if in_use.scalar_one_or_none() is not None:
        raise AppError("national_id_in_use", "national_id_in_use", 409)

    await rate_limit(
        redis,
        f"auth:claimrl:ip:{client_ip(request)}",
        settings.REGISTER_RATE_LIMIT_PER_HOUR,
    )
    # Same metered Shahkar check as registration: the SIM must belong to the owner.
    await verify_mobile_owner(national_id, owner.phone)

    owner.full_name = full_name
    owner.national_id = national_id
    owner.hashed_password = security.hash_password(password)
    owner.is_verified = True
    owner.is_phone_verified = True
    owner.is_national_id_verified = True
    owner.national_id_verified_at = datetime.now(timezone.utc)
    owner.last_login_at = owner.national_id_verified_at
    if owner.role == UserRole.CUSTOMER:
        owner.role = UserRole.OWNER
    await redis.delete(marker)
    await session.commit()
    await session.refresh(owner)

    access, refresh = await issue_tokens(owner)
    return {
        "data": {
            "access": access,
            "refresh": refresh,
            "user": {
                "id": str(owner.id),
                "phone": owner.phone,
                "national_id": owner.national_id,
                "full_name": owner.full_name,
                "role": owner.role.value,
                "permissions": list(owner.permissions or []),
                "is_verified": owner.is_verified,
                "is_phone_verified": owner.is_phone_verified,
                "is_national_id_verified": owner.is_national_id_verified,
                "last_login_at": (
                    owner.last_login_at.isoformat() if owner.last_login_at else None
                ),
                "created_at": owner.created_at.isoformat() if owner.created_at else None,
            },
        }
    }


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
    subcategories = _business_subcategories(business)
    standard_names = _standard_tag_names(subcategories)
    names = _with_hidden_standard_tags(names, subcategories)
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
        "is_license_verified": business.is_license_verified,
    }}


@me_router.get("/me/analytics")
async def my_analytics(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Owner-wide summary for the dashboard analytics page.

    Only a lifetime view counter exists, so the 30-day trend covers likes and
    quote requests, which carry their own timestamps.
    """
    business_ids = list(
        (
            await session.execute(
                sa.select(Business.id).where(
                    Business.owner_id == user.id, Business.deleted_at.is_(None)
                )
            )
        ).scalars()
    )
    if not business_ids:
        return {
            "data": {
                "business_count": 0,
                "view_count": 0,
                "like_count": 0,
                "rating_avg": 0.0,
                "rating_count": 0,
                "quote_requests": 0,
                "quote_responded": 0,
                "series": [],
            }
        }

    views, likes, rating_count, weighted = (
        await session.execute(
            sa.select(
                sa.func.coalesce(sa.func.sum(Business.view_count), 0),
                sa.func.coalesce(sa.func.sum(Business.like_count), 0),
                sa.func.coalesce(sa.func.sum(Business.rating_count), 0),
                sa.func.coalesce(
                    sa.func.sum(Business.rating_avg * Business.rating_count), 0
                ),
            ).where(Business.id.in_(business_ids))
        )
    ).one()
    ratings = int(rating_count or 0)

    quote_requests, quote_responded = (
        await session.execute(
            sa.select(
                sa.func.count(QuoteDelivery.id),
                sa.func.count(QuoteDelivery.responded_at),
            ).where(QuoteDelivery.business_id.in_(business_ids))
        )
    ).one()

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=29)
    since = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)

    def per_day(values: list[datetime]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in values:
            key = value.date().isoformat()
            counts[key] = counts.get(key, 0) + 1
        return counts

    like_times = (
        await session.execute(
            sa.select(BusinessLike.created_at).where(
                BusinessLike.business_id.in_(business_ids),
                BusinessLike.created_at >= since,
            )
        )
    ).scalars().all()
    quote_times = (
        await session.execute(
            sa.select(QuoteDelivery.sent_at).where(
                QuoteDelivery.business_id.in_(business_ids),
                QuoteDelivery.sent_at >= since,
            )
        )
    ).scalars().all()
    like_days = per_day(like_times)
    quote_days = per_day(quote_times)

    series = []
    for offset in range(30):
        key = (start + timedelta(days=offset)).isoformat()
        series.append(
            {
                "date": key,
                "likes": like_days.get(key, 0),
                "quotes": quote_days.get(key, 0),
            }
        )

    return {
        "data": {
            "business_count": len(business_ids),
            "view_count": int(views or 0),
            "like_count": int(likes or 0),
            "rating_avg": round(float(weighted or 0) / ratings, 2) if ratings else 0.0,
            "rating_count": ratings,
            "quote_requests": int(quote_requests or 0),
            "quote_responded": int(quote_responded or 0),
            "series": series,
        }
    }


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


def _mask_phone(phone: str) -> str:
    """Hide the last digits of an owner phone from anonymous visitors."""
    return f"{phone[:-4]}****" if len(phone) > 4 else "****"


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
    view_count = business.view_count or 0
    if business.status == BusinessStatus.APPROVED:
        view_count += 1
        # Viewing must not look like a business edit. The ORM's onupdate would
        # touch updated_at when incrementing view_count, so update the counter
        # with the timestamp pinned to its current value.
        await session.execute(
            sa.update(Business)
            .where(Business.id == business.id)
            .values(
                view_count=sa.func.coalesce(Business.view_count, 0) + 1,
                updated_at=Business.updated_at,
            )
            .execution_options(synchronize_session=False)
        )
    data = _business_payload(BusinessHit(business=business), detail=True)
    data["view_count"] = view_count
    owner = await session.get(User, business.owner_id)
    data["owner"] = (
        {
            "name": (owner.full_name or "").strip() or None,
            # Anonymous visitors only get the masked number; the full phone is
            # available after login (see the public business page gate).
            "phone": owner.phone if user is not None else _mask_phone(owner.phone),
            # The public owner card hides the display name and shows the
            # «مالک تایید هویت نشده» warning until an operator verifies the
            # account (imported or dashboard-created owners start unverified).
            "is_verified": owner.is_verified,
        }
        if owner is not None
        else None
    )
    data["is_owner"] = is_owner
    data["is_saved"] = False
    data["bookmark_note"] = None
    data["is_liked"] = False
    data["my_review"] = None
    if user is not None:
        saved = (
            await session.execute(
                sa.select(Bookmark.note).where(
                    Bookmark.user_id == user.id, Bookmark.business_id == business.id
                )
            )
        ).first()
        data["is_saved"] = saved is not None
        data["bookmark_note"] = saved[0] if saved is not None else None
        liked = (
            await session.execute(
                sa.select(BusinessLike.id).where(
                    BusinessLike.user_id == user.id, BusinessLike.business_id == business.id
                )
            )
        ).scalars().first()
        data["is_liked"] = liked is not None
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
    data["images"] = await _business_images_payload(session, business)
    await session.commit()
    return {"data": data}
