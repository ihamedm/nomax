import re
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.deps import get_current_user, get_otp_service, require_permissions, require_superadmin
from app.core.errors import AppError
from app.core.permissions import has_permission, permission_catalog, validate_permission_codes
from app.db.session import get_db
from app.models.admin import AuditLog
from app.models.user import User, UserRole
from app.schemas.admin import AdminUserCreate, AdminUserResponse, AdminUserUpdate
from app.services.inapp_notifications import (
    notify_business_approved,
    notify_business_rejected,
)
from app.services import dashboard as dashboard_service
from app.services import map_cache
from app.services.otp_service import OtpService

admin_router = APIRouter(prefix="/admin", tags=["admin"])
dev_router = APIRouter(prefix="/admin/dev", tags=["admin-dev"])


router = admin_router


async def _write_audit(
    session: AsyncSession,
    actor_id,
    action: str,
    entity_type: str,
    entity_id: str | None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    ip: Optional[str] = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            ip=ip,
        )
    )
    await session.flush()


def _to_admin_response(user: User) -> dict:
    return AdminUserResponse(
        id=str(user.id),
        phone=user.phone,
        national_id=user.national_id,
        full_name=user.full_name,
        role=user.role.value,
        permissions=list(user.permissions or []),
        is_verified=user.is_verified,
        is_phone_verified=user.is_phone_verified,
        is_national_id_verified=user.is_national_id_verified,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        deleted_at=user.deleted_at,
    ).model_dump(mode="json")


def _clean_text(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


async def _validate_national_id(
    session: AsyncSession, national_id: str | None, *, exclude_id=None
) -> str | None:
    """Normalise and uniqueness-check an operator-supplied national ID."""
    cleaned = _clean_text(national_id)
    if cleaned is None:
        return None
    if not security.validate_iranian_national_id(cleaned):
        raise AppError("validation_error", "invalid_national_id", 422, {"national_id": cleaned})
    query = select(User.id).where(User.national_id == cleaned)
    if exclude_id is not None:
        query = query.where(User.id != exclude_id)
    if (await session.execute(query)).scalar_one_or_none() is not None:
        raise AppError("conflict", "national_id_in_use", 409, {"national_id": cleaned})
    return cleaned


def _admin_business_payload(business, owner: User | None = None) -> dict:
    category = business.category
    subcategory = business.subcategory
    return {
        "id": str(business.id),
        "name": business.name,
        "slug": business.slug,
        "status": business.status.value if hasattr(business.status, "value") else str(business.status),
        "is_verified": business.is_verified,
        "is_24h": business.is_24h,
        "short_description": business.short_description,
        "description": business.description,
        "address": business.address,
        "phone_business": business.phone_business,
        "instagram": business.instagram,
        "geo": (
            {"lat": business.geo_lat, "lng": business.geo_lng}
            if business.geo_lat is not None and business.geo_lng is not None
            else None
        ),
        "category": (
            {"id": category.id, "slug": category.slug, "name": category.name, "icon": category.icon}
            if category is not None
            else None
        ),
        "subcategory": (
            {"id": subcategory.id, "slug": subcategory.slug, "name": subcategory.name, "icon": subcategory.icon}
            if subcategory is not None
            else None
        ),
        "rating_avg": round(business.rating_avg or 0, 2),
        "rating_count": business.rating_count or 0,
        "view_count": business.view_count or 0,
        "profile_image_url": business.profile_image_url,
        "rejection_reason": business.rejection_reason,
        "owner": (
            {
                "id": str(owner.id),
                "phone": owner.phone,
                "full_name": owner.full_name,
                "is_verified": owner.is_verified,
            }
            if owner is not None
            else None
        ),
        "created_at": business.created_at.isoformat() if business.created_at else None,
        "updated_at": business.updated_at.isoformat() if business.updated_at else None,
        "deleted_at": business.deleted_at.isoformat() if business.deleted_at else None,
    }


async def _admin_business_detail_payload(session: AsyncSession, business, owner: User | None = None) -> dict:
    """Business payload plus gallery and tags, used by the add/edit wizard."""
    from app.api.v1.businesses import _business_images_payload
    from app.models.tag import BusinessTag, Tag

    data = _admin_business_payload(business, owner)
    data["images"] = await _business_images_payload(session, business)
    data["tags"] = list(
        (
            await session.execute(
                select(Tag.name)
                .join(BusinessTag, BusinessTag.tag_id == Tag.id)
                .where(BusinessTag.business_id == business.id)
                .order_by(Tag.name)
            )
        )
        .scalars()
        .all()
    )
    return data


def _require_any_permission(*codes: str):
    async def _require(actor: User = Depends(get_current_user)) -> User:
        if not any(has_permission(actor, code) for code in codes):
            raise AppError("forbidden", "permission_denied", 403, {"permissions": list(codes)})
        return actor

    return _require


async def _get_admin_business(session: AsyncSession, business_id: str):
    from app.models.business import Business

    try:
        bid = UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None or business.deleted_at is not None:
        raise AppError("not_found", "business_not_found", 404)
    return business


@router.get("/me")
async def admin_me(user: User = Depends(get_current_user)) -> dict:
    return {"data": {"user": _to_admin_response(user), "is_superadmin": user.role == UserRole.SUPERADMIN}}


@router.get("/businesses")
async def list_admin_businesses(
    status: Optional[str] = None,
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    owner_id: Optional[str] = None,
    trash: bool = False,
    page: int = 1,
    per_page: int = 20,
    actor: User = Depends(require_permissions("business.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    from app.models.business import Business

    page = max(1, page)
    per_page = min(100, max(1, per_page))
    conditions = [Business.deleted_at.is_not(None) if trash else Business.deleted_at.is_(None)]
    if status:
        conditions.append(Business.status == status)
    if category_id:
        conditions.append(Business.category_id == category_id)
    if owner_id:
        try:
            conditions.append(Business.owner_id == UUID(owner_id))
        except ValueError:
            raise AppError("validation_error", "invalid_owner_id", 422, {"owner_id": owner_id})
    if q:
        term = f"%{q.strip()}%"
        conditions.append(
            or_(Business.name.ilike(term), Business.slug.ilike(term))
        )

    total = int(
        (await session.execute(select(func.count(Business.id)).where(*conditions))).scalar() or 0
    )
    rows = (
        await session.execute(
            select(Business, User)
            .join(User, Business.owner_id == User.id)
            .where(*conditions)
            .order_by(Business.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    pages = max(1, (total + per_page - 1) // per_page)
    return {
        "data": {"items": [_admin_business_payload(b, owner) for b, owner in rows]},
        "meta": {"page": page, "per_page": per_page, "total": total, "pages": pages},
    }


@router.post("/businesses")
async def create_admin_business(
    payload: dict,
    request: Request,
    actor: User = Depends(require_permissions("business.create")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.api.v1.businesses import (
        _assign_tags,
        _clean_tags,
        _replace_business_images,
        _resolve_business_images,
    )
    from app.models.business import Business, BusinessStatus
    from app.models.category import Category, Subcategory

    name = (payload.get("name") or "").strip()
    address = (payload.get("address") or "").strip()
    if not name or payload.get("category_id") is None or not address:
        raise AppError("validation_error", "name_address_category_required", 422)

    if payload.get("owner_id"):
        try:
            owner_id = UUID(str(payload["owner_id"]))
        except ValueError:
            raise AppError("validation_error", "invalid_owner_id", 422)
        owner = await session.get(User, owner_id)
    elif payload.get("owner_phone"):
        owner_phone = security.normalize_phone(payload["owner_phone"])
        owner = (
            await session.execute(select(User).where(User.phone == owner_phone))
        ).scalars().first()
    else:
        raise AppError("validation_error", "owner_required", 422)
    if owner is None or owner.deleted_at is not None:
        raise AppError("not_found", "owner_not_found", 404)
    if owner.role == UserRole.CUSTOMER:
        owner.role = UserRole.OWNER

    category = await session.get(Category, payload["category_id"])
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

    images, profile_image_url = _resolve_business_images(payload)
    tags = _clean_tags(payload.get("tags"))

    status_value = payload.get("status") or BusinessStatus.PENDING.value
    if status_value not in [item.value for item in BusinessStatus]:
        raise AppError("validation_error", "invalid_status", 422)

    slug_base = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-") or "business"
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        subcategory_id=subcategory_id,
        name=name,
        slug=f"{slug_base}-{uuid.uuid4().hex[:6]}",
        short_description=(payload.get("short_description") or "")[:120],
        description=payload.get("description"),
        phone_business=phone_business,
        address=address,
        geo_lat=geo_lat,
        geo_lng=geo_lng,
        instagram=instagram,
        is_24h=bool(payload.get("is_24h", False)),
        is_verified=bool(payload.get("is_verified", False)),
        profile_image_url=profile_image_url,
        rejection_reason=(payload.get("rejection_reason") or None) if status_value == "rejected" else None,
        status=BusinessStatus(status_value),
    )
    session.add(business)
    await session.flush()

    if images:
        await _replace_business_images(session, business.id, images)
    if tags:
        await _assign_tags(
            session,
            business.id,
            tags,
            standard_names=set(subcategory.standard_tags or []) if subcategory else set(),
        )
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.business.created",
        entity_type="business",
        entity_id=str(business.id),
        after={"name": business.name, "owner_id": str(owner.id)},
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(business)
    return {"data": await _admin_business_detail_payload(session, business, owner)}


@router.get("/businesses/owners")
async def search_business_owners(
    q: Optional[str] = Query(None, max_length=120),
    limit: int = Query(20, ge=1, le=50),
    actor: User = Depends(_require_any_permission("business.read", "business.create", "business.update")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Owners/customers an operator can assign as a business owner."""
    del actor
    conditions = [
        User.deleted_at.is_(None),
        User.role.in_([UserRole.CUSTOMER, UserRole.OWNER]),
    ]
    term = (q or "").strip()
    if term:
        clauses = [User.full_name.ilike(f"%{term}%")]
        digits = "".join(ch for ch in term if ch.isdigit())
        if digits.startswith("98") and len(digits) > 10:
            digits = digits[2:]
        digits = digits.lstrip("0")
        if digits:
            clauses.append(User.phone.ilike(f"%{digits}%"))
        conditions.append(or_(*clauses))
    rows = (
        await session.execute(
            select(User).where(*conditions).order_by(User.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return {
        "data": {
            "items": [
                {
                    "id": str(user.id),
                    "phone": user.phone,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "is_verified": user.is_verified,
                }
                for user in rows
            ]
        }
    }


@router.post("/businesses/owners")
async def create_business_owner(
    payload: dict,
    request: Request,
    actor: User = Depends(require_permissions("business.create")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create an owner inline from the business form."""
    phone = security.normalize_phone(payload.get("phone") or "")
    existing = (await session.execute(select(User).where(User.phone == phone))).scalars().first()
    if existing is not None:
        raise AppError("conflict", "user_already_exists", 409, {"phone": phone})
    national_id = await _validate_national_id(session, payload.get("national_id"))
    full_name = _clean_text(payload.get("full_name"))
    owner = User(
        phone=phone,
        national_id=national_id,
        full_name=full_name[:120] if full_name else None,
        role=UserRole.OWNER,
    )
    session.add(owner)
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.owner.created",
        entity_type="user",
        entity_id=str(owner.id),
        after={"phone": owner.phone, "full_name": owner.full_name},
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(owner)
    return {
        "data": {
            "id": str(owner.id),
            "phone": owner.phone,
            "full_name": owner.full_name,
            "role": owner.role.value,
            "is_verified": owner.is_verified,
        }
    }


@router.get("/businesses/{business_id}")
async def get_admin_business(
    business_id: str,
    actor: User = Depends(_require_any_permission("business.read", "business.update")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    business = await _get_admin_business(session, business_id)
    owner = await session.get(User, business.owner_id)
    return {"data": await _admin_business_detail_payload(session, business, owner)}


@router.patch("/businesses/{business_id}")
async def update_admin_business(
    business_id: str,
    payload: dict,
    request: Request,
    actor: User = Depends(require_permissions("business.update")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.api.v1.businesses import (
        _assign_tags,
        _clean_tags,
        _replace_business_images,
        _resolve_business_images,
    )
    from app.models.business import BusinessStatus
    from app.models.category import Category, Subcategory

    business = await _get_admin_business(session, business_id)
    before = {
        "status": business.status.value,
        "name": business.name,
        "owner_id": str(business.owner_id),
    }
    previous_status = business.status

    if "owner_id" in payload:
        try:
            owner_id = UUID(str(payload["owner_id"]))
        except ValueError:
            raise AppError("validation_error", "invalid_owner_id", 422)
        new_owner = await session.get(User, owner_id)
        if new_owner is None or new_owner.deleted_at is not None:
            raise AppError("not_found", "owner_not_found", 404)
        if new_owner.role == UserRole.CUSTOMER:
            new_owner.role = UserRole.OWNER
        business.owner_id = new_owner.id

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
    business.category_id = category.id
    business.subcategory_id = new_subcategory_id

    editable = (
        "name",
        "short_description",
        "description",
        "phone_business",
        "address",
        "instagram",
        "is_24h",
        "is_verified",
    )
    for field in editable:
        if field in payload:
            setattr(business, field, payload[field])

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
    business.geo_lat = geo_lat
    business.geo_lng = geo_lng

    if "phone_business" in payload:
        phone_business = (payload.get("phone_business") or "").strip() or None
        if phone_business and not re.fullmatch(r"0\d{10}", phone_business):
            raise AppError("validation_error", "invalid_phone_business", 422)
        business.phone_business = phone_business

    if "instagram" in payload:
        instagram = (payload.get("instagram") or "").strip() or None
        if instagram and len(instagram) > 100:
            raise AppError("validation_error", "instagram_too_long", 422)
        business.instagram = instagram

    images, profile_image_url = _resolve_business_images(payload)
    images_changed = "images" in payload or "profile_image_url" in payload
    if not images_changed:
        profile_image_url = business.profile_image_url
    business.profile_image_url = profile_image_url
    tags = _clean_tags(payload.get("tags")) if "tags" in payload else None

    if "rejection_reason" in payload:
        business.rejection_reason = (payload.get("rejection_reason") or "").strip() or None
    if "status" in payload:
        if payload["status"] not in [item.value for item in BusinessStatus]:
            raise AppError("validation_error", "invalid_status", 422)
        business.status = BusinessStatus(payload["status"])
        if business.status != BusinessStatus.REJECTED and "rejection_reason" not in payload:
            business.rejection_reason = None

    if images_changed:
        await _replace_business_images(session, business.id, images)
    if tags is not None:
        await _assign_tags(
            session,
            business.id,
            tags,
            standard_names=set(subcategory.standard_tags or []) if subcategory else set(),
        )

    if business.status != previous_status:
        if business.status == BusinessStatus.REJECTED:
            await notify_business_rejected(
                session,
                owner_id=business.owner_id,
                business_id=business.id,
                business_slug=business.slug,
                business_name=business.name,
                reason=business.rejection_reason,
            )
        elif business.status == BusinessStatus.APPROVED:
            await notify_business_approved(
                session,
                owner_id=business.owner_id,
                business_id=business.id,
                business_slug=business.slug,
                business_name=business.name,
            )
    await map_cache.enqueue_refresh(session)
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.business.updated",
        entity_type="business",
        entity_id=str(business.id),
        before=before,
        after={"status": business.status.value, "name": business.name},
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(business)
    owner = await session.get(User, business.owner_id)
    return {"data": await _admin_business_detail_payload(session, business, owner)}


@router.delete("/businesses/{business_id}")
async def delete_admin_business(
    business_id: str,
    request: Request,
    actor: User = Depends(require_permissions("business.delete")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Soft-delete a business (move to trash)."""
    from datetime import datetime, timezone

    business = await _get_admin_business(session, business_id)
    business.deleted_at = datetime.now(timezone.utc)
    await map_cache.enqueue_refresh(session)
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.business.deleted",
        entity_type="business",
        entity_id=str(business.id),
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return {"data": {"id": str(business.id), "deleted": True}}


@router.post("/businesses/{business_id}/restore")
async def restore_admin_business(
    business_id: str,
    request: Request,
    actor: User = Depends(require_permissions("business.delete")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Restore a soft-deleted business from trash."""
    try:
        bid = UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    from app.models.business import Business

    business = await session.get(Business, bid)
    if business is None or business.deleted_at is None:
        raise AppError("not_found", "business_not_found", 404)

    business.deleted_at = None
    await map_cache.enqueue_refresh(session)
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.business.restored",
        entity_type="business",
        entity_id=str(business_id),
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(business)
    owner = await session.get(User, business.owner_id)
    return {"data": await _admin_business_detail_payload(session, business, owner)}


@router.delete("/businesses/{business_id}/permanent")
async def delete_admin_business_permanently(
    business_id: str,
    request: Request,
    actor: User = Depends(require_permissions("business.delete")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Hard-delete a trashed business from the database.

    Checks for related data (reviews, offers, licenses) and blocks deletion
    until those are removed first, so data is not orphaned.
    """
    try:
        bid = UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    from app.models.business import Business, BusinessImage
    from app.models.review import Review
    from app.models.license import License
    from app.models.quote import Offer
    from app.models.tag import BusinessTag
    from app.models.bookmark import Bookmark
    from app.models.analytics import QuoteDelivery

    business = await session.get(Business, bid)
    if business is None or business.deleted_at is None:
        raise AppError("not_found", "business_not_found", 404)

    related: list[tuple[str, str, int]] = []

    reviews = await session.scalar(
        select(func.count()).select_from(Review).where(
            Review.business_id == bid, Review.deleted_at.is_(None)
        )
    )
    if reviews:
        related.append(("reviews", "نظر", reviews))

    offers = await session.scalar(
        select(func.count()).select_from(Offer).where(
            Offer.business_id == bid, Offer.deleted_at.is_(None)
        )
    )
    if offers:
        related.append(("offers", "پیشنهاد قیمت", offers))

    license_row = await session.scalar(
        select(func.count()).select_from(License).where(
            License.business_id == bid, License.deleted_at.is_(None)
        )
    )
    if license_row:
        related.append(("licenses", "مجوز", license_row))

    if related:
        summary = "، ".join(f"{label} ({count})" for _, label, count in related)
        raise AppError(
            "business_has_relations",
            f"این کسب‌وکار {summary} دارد. ابتدا آن‌ها را حذف کنید.",
            409,
            {"related": [{"type": t, "count": c} for t, _, c in related]},
        )

    # Child rows follow ON DELETE CASCADE, but the test database does not
    # enforce foreign keys; delete them explicitly so no rows are orphaned.
    await session.execute(delete(BusinessImage).where(BusinessImage.business_id == bid))
    await session.execute(delete(BusinessTag).where(BusinessTag.business_id == bid))
    await session.execute(delete(Bookmark).where(Bookmark.business_id == bid))
    await session.execute(delete(QuoteDelivery).where(QuoteDelivery.business_id == bid))
    await session.execute(delete(License).where(License.business_id == bid))
    await session.execute(delete(Review).where(Review.business_id == bid))
    await session.execute(delete(Offer).where(Offer.business_id == bid))

    await map_cache.enqueue_refresh(session)
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.business.permanently_deleted",
        entity_type="business",
        entity_id=str(business_id),
        before={"name": business.name, "slug": business.slug},
        ip=request.client.host if request.client else None,
    )
    await session.delete(business)
    await session.commit()
    return {"data": {"id": str(business_id), "deleted": True, "permanent": True}}


@router.patch("/businesses/{business_id}/verify-license")
async def verify_license(
    business_id: str,
    actor: User = Depends(require_permissions("business.license.verify")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.business import Business
    from app.models.license import License

    try:
        from uuid import UUID as _UUID

        bid = _UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None:
        raise AppError("not_found", "business_not_found", 404)
    license_row = (
        await session.execute(
            select(License).where(License.business_id == bid, License.deleted_at.is_(None))
        )
    ).scalars().first()
    if license_row is None:
        raise AppError("not_found", "license_not_found", 404)
    license_row.is_verified_by_admin = True
    business.is_verified = True
    await _write_audit(session, actor.id, "business.license.verify", "business", str(bid), after={"verified": True})
    await session.commit()
    return {"data": {"id": str(bid), "is_verified": True}}


@router.patch("/businesses/{business_id}/toggle-24h")
async def toggle_24h(
    business_id: str,
    actor: User = Depends(require_permissions("business.approve")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.business import Business

    try:
        from uuid import UUID as _UUID

        bid = _UUID(business_id)
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    business = await session.get(Business, bid)
    if business is None:
        raise AppError("not_found", "business_not_found", 404)
    business.is_24h = not business.is_24h
    await _write_audit(session, actor.id, "business.toggle_24h", "business", str(bid), after={"is_24h": business.is_24h})
    await session.commit()
    return {"data": {"id": str(bid), "is_24h": business.is_24h}}


@router.patch("/businesses/{business_id}/approve")
async def approve_business(
    business_id: str,
    actor: User = Depends(require_permissions("business.approve")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.business import Business, BusinessStatus
    from uuid import UUID as _UUID

    bid = _UUID(business_id)
    business = await session.get(Business, bid)
    if business is None:
        raise AppError("not_found", "business_not_found", 404)
    was_approved = business.status == BusinessStatus.APPROVED
    business.status = BusinessStatus.APPROVED
    business.rejection_reason = None
    if not was_approved:
        await notify_business_approved(
            session,
            owner_id=business.owner_id,
            business_id=business.id,
            business_slug=business.slug,
            business_name=business.name,
        )
    if not was_approved:
        # The public map reads a Redis snapshot; refresh it from the worker.
        await map_cache.enqueue_refresh(session)
    await _write_audit(session, actor.id, "business.approve", "business", str(bid), after={"status": "approved"})
    await session.commit()
    return {"data": {"id": str(bid), "status": "approved"}}


@router.patch("/businesses/{business_id}/reject")
async def reject_business(
    business_id: str,
    payload: dict,
    actor: User = Depends(require_permissions("business.approve")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.business import Business, BusinessStatus
    from uuid import UUID as _UUID

    bid = _UUID(business_id)
    business = await session.get(Business, bid)
    if business is None:
        raise AppError("not_found", "business_not_found", 404)
    reason = (payload.get("reason") or "").strip()
    if not reason:
        raise AppError("rejection_reason_required", "rejection_reason_required", 422)
    business.status = BusinessStatus.REJECTED
    business.rejection_reason = reason
    await notify_business_rejected(
        session,
        owner_id=business.owner_id,
        business_id=business.id,
        business_name=business.name,
        reason=reason,
    )
    await map_cache.enqueue_refresh(session)
    await _write_audit(session, actor.id, "business.reject", "business", str(bid), after={"reason": business.rejection_reason})
    await session.commit()
    return {"data": {"id": str(bid), "status": "rejected"}}


@router.get("/reviews/businesses")
async def list_review_businesses(
    actor: User = Depends(require_permissions("review.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    from app.models.business import Business
    from app.models.review import Review

    rows = (
        await session.execute(
            select(Business.id, Business.name)
            .join(Review, Review.business_id == Business.id)
            .where(
                Business.deleted_at.is_(None),
                Review.deleted_at.is_(None),
                Review.is_private.is_(False),
            )
            .group_by(Business.id, Business.name)
            .order_by(Business.name)
        )
    ).all()
    return {"data": {"items": [{"id": str(bid), "name": name} for bid, name in rows]}}


@router.get("/reviews")
async def list_admin_reviews(
    status: Optional[str] = None,
    business_id: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    actor: User = Depends(require_permissions("review.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    from app.models.business import Business
    from app.models.review import Review

    page = max(1, page)
    per_page = min(100, max(1, per_page))
    conditions = [
        Review.deleted_at.is_(None),
        Review.is_private.is_(False),
        Business.deleted_at.is_(None),
    ]
    if status:
        if status not in ("approved", "pending", "rejected", "unapproved"):
            raise AppError("validation_error", "invalid_status", 422)
        conditions.append(
            Review.status == ("pending" if status == "unapproved" else status)
        )
    if business_id:
        try:
            conditions.append(Review.business_id == uuid.UUID(business_id))
        except ValueError:
            raise AppError("validation_error", "invalid_business_id", 422)
    if q:
        term = f"%{q.strip()}%"
        conditions.append(
            or_(
                Business.name.ilike(term),
                Review.author_name.ilike(term),
                Review.text.ilike(term),
            )
        )

    total = int(
        (
            await session.execute(
                select(func.count(Review.id))
                .select_from(Review)
                .join(Business, Review.business_id == Business.id)
                .where(*conditions)
            )
        ).scalar()
        or 0
    )
    rows = (
        await session.execute(
            select(Review, Business.name, Business.slug)
            .join(Business, Review.business_id == Business.id)
            .where(*conditions)
            .order_by(Review.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    pages = max(1, (total + per_page - 1) // per_page)
    return {
        "data": {
            "items": [
                {
                    "id": str(r.id),
                    "business_id": str(r.business_id),
                    "business_name": business_name,
                    "business_slug": business_slug,
                    "rating": r.rating,
                    "text": r.text,
                    "author_name": r.author_name,
                    "reply": r.reply,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r, business_name, business_slug in rows
            ]
        },
        "meta": {"page": page, "per_page": per_page, "total": total, "pages": pages},
    }


@router.get("/stats/overview")
async def stats_overview(
    actor: User = Depends(require_permissions("stats.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    from app.models.business import Business

    async def count(condition=None):
        stmt = select(func.count(Business.id))
        if condition is not None:
            stmt = stmt.where(condition)
        return int((await session.execute(stmt)).scalar() or 0)

    return {"data": {
        "pending": await count(Business.status == "pending"),
        "approved": await count(Business.status == "approved"),
        "rejected": await count(Business.status == "rejected"),
        "urgent": await count(Business.is_24h.is_(True)),
    }}


@router.get("/dashboard")
async def dashboard(
    days: int = Query(14, ge=7, le=30),
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Single-shot payload for the admin home page.

    Analytics blocks are omitted for admins without `stats.read`; actionable
    queues are filtered by the permissions the viewer actually holds.
    """
    is_super = actor.role == UserRole.SUPERADMIN
    return {
        "data": await dashboard_service.overview(
            session,
            days=days,
            can_stats=is_super or has_permission(actor, "stats.read"),
            can_business=is_super or has_permission(actor, "business.read"),
            can_review=is_super or has_permission(actor, "review.read"),
            can_quote=is_super or has_permission(actor, "quote.read"),
        )
    }


@router.get("/attention")
async def attention_counts(
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Pending work the viewer can action, for the admin header badge."""
    from app.models.business import Business
    from app.models.review import Review

    is_super = actor.role == UserRole.SUPERADMIN
    businesses = 0
    reviews = 0
    if is_super or has_permission(actor, "business.read"):
        businesses = int(
            (
                await session.execute(
                    select(func.count(Business.id)).where(
                        Business.deleted_at.is_(None), Business.status == "pending"
                    )
                )
            ).scalar()
            or 0
        )
    if is_super or has_permission(actor, "review.read"):
        reviews = int(
            (
                await session.execute(
                    select(func.count(Review.id)).where(
                        Review.deleted_at.is_(None),
                        Review.is_private.is_(False),
                        Review.status == "pending",
                    )
                )
            ).scalar()
            or 0
        )
    return {
        "data": {"businesses": businesses, "reviews": reviews, "total": businesses + reviews}
    }


@router.get("/audit-log")
async def list_audit_log(
    actor: User = Depends(require_permissions("admin.audit.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    rows = (
        await session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(100))
    ).scalars().all()
    return {
        "data": {
            "items": [
                {
                    "id": row.id,
                    "actor_id": str(row.actor_id),
                    "action": row.action,
                    "entity_type": row.entity_type,
                    "entity_id": row.entity_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        }
    }


@router.get("/permissions")
async def list_permissions(actor: User = Depends(require_superadmin)) -> dict:
    del actor
    return {"data": {"items": permission_catalog()}}


@router.get("/users")
async def list_users(
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
    role: Optional[UserRole] = Query(None),
    verified: Optional[bool] = Query(None),
    trash: bool = Query(False),
    q: Optional[str] = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> dict:
    del actor  # superadmin gate already enforced via dependency
    conditions = [User.deleted_at.is_not(None) if trash else User.deleted_at.is_(None)]
    if role is not None:
        conditions.append(User.role == role)
    if verified is not None:
        conditions.append(User.is_verified.is_(verified))

    term = (q or "").strip()
    if term:
        clauses = [User.full_name.ilike(f"%{term}%")]
        # Phones are stored as 10 digits without the leading 0/98 prefix, so
        # accept operator input such as "0912…" or "+98912…" as well.
        digits = "".join(ch for ch in term if ch.isdigit())
        if digits.startswith("98") and len(digits) > 10:
            digits = digits[2:]
        digits = digits.lstrip("0")
        if digits:
            clauses.append(User.phone.ilike(f"%{digits}%"))
        conditions.append(or_(*clauses))

    total = int(
        (await session.execute(select(func.count(User.id)).where(*conditions))).scalar() or 0
    )
    rows = (
        await session.execute(
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc(), User.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).scalars().all()
    pages = max(1, (total + per_page - 1) // per_page)
    return {
        "data": {"items": [_to_admin_response(u) for u in rows]},
        "meta": {"page": page, "per_page": per_page, "total": total, "pages": pages},
    }


@router.post("/users")
async def create_user(
    payload: AdminUserCreate,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    phone = security.normalize_phone(payload.phone)
    existing = (
        await session.execute(select(User).where(User.phone == phone))
    ).scalars().first()
    if existing is not None:
        raise AppError("conflict", "user_already_exists", 409, {"phone": phone})

    national_id = await _validate_national_id(session, payload.national_id)
    permissions = (
        validate_permission_codes(payload.permissions or [])
        if payload.role == UserRole.ADMIN
        else []
    )
    user = User(
        phone=phone,
        national_id=national_id,
        full_name=_clean_text(payload.full_name),
        role=payload.role,
        permissions=permissions,
        is_verified=payload.is_verified,
        is_phone_verified=payload.is_phone_verified,
    )
    session.add(user)
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.user.created",
        entity_type="user",
        entity_id=str(user.id),
        after={
            "role": user.role.value,
            "permissions": permissions,
            "is_verified": user.is_verified,
        },
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(user)
    return {"data": _to_admin_response(user)}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    target = await session.get(User, UUID(user_id))
    if target is None:
        raise AppError("not_found", "user_not_found", 404)

    provided = payload.model_fields_set
    before = {
        "full_name": target.full_name,
        "national_id": target.national_id,
        "role": target.role.value,
        "permissions": list(target.permissions or []),
        "is_verified": target.is_verified,
        "is_phone_verified": target.is_phone_verified,
    }

    if "full_name" in provided:
        target.full_name = _clean_text(payload.full_name)
    if "national_id" in provided:
        target.national_id = await _validate_national_id(
            session, payload.national_id, exclude_id=target.id
        )

    if payload.role is not None and payload.role != target.role:
        if target.id == actor.id and payload.role != UserRole.SUPERADMIN:
            raise AppError("conflict", "cannot_change_own_role", 409)
        if target.role == UserRole.SUPERADMIN and payload.role != UserRole.SUPERADMIN:
            remaining = await session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.role == UserRole.SUPERADMIN,
                    User.deleted_at.is_(None),
                    User.id != target.id,
                )
            )
            if not remaining:
                raise AppError("conflict", "last_superadmin_required", 409)
        target.role = payload.role
        # A demoted admin must not keep dormant grants.
        if target.role != UserRole.ADMIN:
            target.permissions = []

    if payload.permissions is not None:
        target.permissions = (
            validate_permission_codes(payload.permissions)
            if target.role == UserRole.ADMIN
            else []
        )

    if payload.is_verified is not None:
        target.is_verified = payload.is_verified
    if payload.is_phone_verified is not None:
        target.is_phone_verified = payload.is_phone_verified

    after = {
        "full_name": target.full_name,
        "national_id": target.national_id,
        "role": target.role.value,
        "permissions": list(target.permissions or []),
        "is_verified": target.is_verified,
        "is_phone_verified": target.is_phone_verified,
    }
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.user.updated",
        entity_type="user",
        entity_id=str(user_id),
        before=before,
        after=after,
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(target)
    return {"data": _to_admin_response(target)}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Soft-delete a user account.

    The row is kept so owned businesses, quotes and reviews stay referentially
    intact; `deleted_at` hides the account from lists and invalidates its
    access tokens (see `get_current_user`).
    """
    from datetime import datetime, timezone

    target = await session.get(User, UUID(user_id))
    if target is None or target.deleted_at is not None:
        raise AppError("not_found", "user_not_found", 404)
    if target.id == actor.id:
        raise AppError("conflict", "cannot_delete_self", 409)
    if target.role == UserRole.SUPERADMIN:
        remaining = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == UserRole.SUPERADMIN,
                User.deleted_at.is_(None),
                User.id != target.id,
            )
        )
        if not remaining:
            raise AppError("conflict", "last_superadmin_required", 409)

    before = {
        "phone": target.phone,
        "full_name": target.full_name,
        "role": target.role.value,
        "permissions": list(target.permissions or []),
    }
    target.deleted_at = datetime.now(timezone.utc)
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.user.deleted",
        entity_type="user",
        entity_id=str(user_id),
        before=before,
        after=None,
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return {"data": {"id": str(user_id), "deleted": True}}


@router.post("/users/{user_id}/restore")
async def restore_user(
    user_id: str,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Undelete a soft-deleted user (Trash → بازیابی)."""
    target = await session.get(User, UUID(user_id))
    if target is None or target.deleted_at is None:
        raise AppError("not_found", "user_not_found", 404)
    target.deleted_at = None
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.user.restored",
        entity_type="user",
        entity_id=str(user_id),
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return {"data": {"id": str(user_id), "restored": True}}


@router.delete("/users/{user_id}/permanent")
async def delete_user_permanently(
    user_id: str,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Hard-delete a soft-deleted user's row so its phone can register again.

    Children follow their ON DELETE rules (cascades / set-null). Businesses
    RESTRICT on owner: live ones must be transferred or deleted first, while
    already-trashed ones go with the user (otherwise a user who only ever had
    a deleted business could never be purged).
    """
    target = await session.get(User, UUID(user_id))
    if target is None or target.deleted_at is None:
        raise AppError("not_found", "user_not_found", 404)
    from app.models.business import Business

    live_businesses = await session.scalar(
        select(func.count())
        .select_from(Business)
        .where(Business.owner_id == target.id, Business.deleted_at.is_(None))
    )
    if live_businesses:
        raise AppError("user_has_businesses", "user_has_businesses", 409, {"count": live_businesses})
    trashed_businesses = await session.scalar(
        select(func.count()).select_from(Business).where(Business.owner_id == target.id)
    )
    if trashed_businesses:
        await session.execute(delete(Business).where(Business.owner_id == target.id))
        await map_cache.enqueue_refresh(session)
    # Audit-log rows RESTRICT on actor_id; the user is gone, so its own trail goes too.
    await session.execute(delete(AuditLog).where(AuditLog.actor_id == target.id))
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.user.permanently_deleted",
        entity_type="user",
        entity_id=str(user_id),
        before={
            "phone": target.phone,
            "full_name": target.full_name,
            "role": target.role.value,
            "trashed_businesses_deleted": trashed_businesses,
        },
        ip=request.client.host if request.client else None,
    )
    await session.delete(target)
    await session.commit()
    return {"data": {"id": str(user_id), "deleted": True, "permanent": True}}


@router.patch("/users/{user_id}/role")
async def patch_user_role(
    user_id: str,
    payload: AdminUserUpdate,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    target = await session.get(User, UUID(user_id))
    if target is None:
        raise AppError("not_found", "user_not_found", 404)

    if payload.role is not None:
        if target.id == actor.id and payload.role != UserRole.SUPERADMIN:
            raise AppError("conflict", "cannot_change_own_role", 409)
        if target.role == UserRole.SUPERADMIN and payload.role != UserRole.SUPERADMIN:
            remaining = await session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.role == UserRole.SUPERADMIN,
                    User.deleted_at.is_(None),
                    User.id != target.id,
                )
            )
            if not remaining:
                raise AppError("conflict", "last_superadmin_required", 409)

    before = {"role": target.role.value, "permissions": list(target.permissions or [])}
    if payload.role is not None:
        target.role = payload.role
        # Drop dormant grants: a re-promoted admin must start from an explicit
        # set, not from permissions left over before demotion.
        if payload.role != UserRole.ADMIN:
            target.permissions = []
    if payload.permissions is not None:
        target.permissions = validate_permission_codes(payload.permissions)
    after = {"role": target.role.value, "permissions": list(target.permissions or [])}
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.user.role.updated",
        entity_type="user",
        entity_id=str(user_id),
        before=before,
        after=after,
        ip=request.client.host if request.client else None,
    )
    return {"data": {"status": "updated"}}


@router.patch("/users/{user_id}/permissions")
async def patch_user_permissions(
    user_id: str,
    payload: AdminUserUpdate,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    target = await session.get(User, UUID(user_id))
    if target is None:
        raise AppError("not_found", "user_not_found", 404)
    before = list(target.permissions or [])
    if payload.permissions is not None:
        target.permissions = validate_permission_codes(payload.permissions)
    after = list(target.permissions or [])
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.user.permissions.updated",
        entity_type="user",
        entity_id=str(user_id),
        before=before,
        after=after,
        ip=request.client.host if request.client else None,
    )
    return {"data": {"status": "updated"}}


def _dev_otp_item(phone: str, code: str, ttl_seconds: int) -> dict:
    from datetime import datetime, timedelta, timezone

    expires_at = None
    if ttl_seconds > 0:
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
    return {"phone": phone, "otp": code, "ttl_seconds": ttl_seconds, "expires_at": expires_at}


@dev_router.get("/otps")
async def dev_list_otps(
    actor: User = Depends(require_superadmin),
    otp_service: OtpService = Depends(get_otp_service),
) -> dict:
    del actor
    items = [_dev_otp_item(phone, code, ttl) for phone, code, ttl in await otp_service.list_dev_otps()]
    return {"data": {"items": items}}


@dev_router.get("/otps/{phone}")
async def dev_otp(
    phone: str,
    actor: User = Depends(require_superadmin),
    otp_service: OtpService = Depends(get_otp_service),
) -> dict:
    del actor
    normalized = security.normalize_phone(phone)
    code = await otp_service.get_dev_otp(normalized)
    if code is None:
        raise AppError("not_found", "dev_otp_not_found", 404, {"phone": normalized})
    ttl = int(await otp_service.redis.ttl(f"dev:otp:{normalized}"))
    return {"data": _dev_otp_item(normalized, code, ttl)}


__all__ = ["admin_router", "dev_router"]
