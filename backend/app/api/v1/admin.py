import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.deps import get_current_user, get_otp_service, require_permissions, require_superadmin
from app.core.errors import AppError
from app.core.permissions import permission_catalog, validate_permission_codes
from app.db.session import get_db
from app.models.admin import AuditLog
from app.models.user import User, UserRole
from app.schemas.admin import AdminUserResponse, AdminUserUpdate
from app.services.inapp_notifications import (
    notify_business_approved,
    notify_business_rejected,
)
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
        full_name=user.full_name,
        role=user.role.value,
        permissions=list(user.permissions or []),
        is_phone_verified=user.is_phone_verified,
        created_at=user.created_at,
    ).model_dump(mode="json")


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
            {"id": category.id, "slug": category.slug, "name": category.name}
            if category is not None
            else None
        ),
        "subcategory": (
            {"id": subcategory.id, "slug": subcategory.slug, "name": subcategory.name}
            if subcategory is not None
            else None
        ),
        "rating_avg": round(business.rating_avg or 0, 2),
        "rating_count": business.rating_count or 0,
        "view_count": business.view_count or 0,
        "rejection_reason": business.rejection_reason,
        "owner": (
            {"id": str(owner.id), "phone": owner.phone, "full_name": owner.full_name}
            if owner is not None
            else None
        ),
        "created_at": business.created_at.isoformat() if business.created_at else None,
        "updated_at": business.updated_at.isoformat() if business.updated_at else None,
    }


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
    page: int = 1,
    per_page: int = 20,
    actor: User = Depends(require_permissions("business.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    from app.models.business import Business

    page = max(1, page)
    per_page = min(100, max(1, per_page))
    conditions = [Business.deleted_at.is_(None)]
    if status:
        conditions.append(Business.status == status)
    if category_id:
        conditions.append(Business.category_id == category_id)
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
    from app.models.business import Business, BusinessStatus
    from app.models.category import Category

    name = (payload.get("name") or "").strip()
    address = (payload.get("address") or "").strip()
    if not name or payload.get("category_id") is None or not address:
        raise AppError("validation_error", "name_address_category_required", 422)
    if not payload.get("owner_phone"):
        raise AppError("validation_error", "owner_phone_required", 422)
    owner_phone = security.normalize_phone(payload["owner_phone"])
    owner = (
        await session.execute(select(User).where(User.phone == owner_phone))
    ).scalars().first()
    if owner is None or owner.deleted_at is not None:
        raise AppError("not_found", "owner_not_found", 404)
    category = await session.get(Category, payload["category_id"])
    if category is None or category.deleted_at is not None:
        raise AppError("not_found", "category_not_found", 404)
    status_value = payload.get("status") or BusinessStatus.PENDING.value
    if status_value not in [item.value for item in BusinessStatus]:
        raise AppError("validation_error", "invalid_status", 422)

    slug_base = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-") or "business"
    business = Business(
        owner_id=owner.id,
        category_id=payload["category_id"],
        subcategory_id=payload.get("subcategory_id"),
        name=name,
        slug=f"{slug_base}-{uuid.uuid4().hex[:6]}",
        short_description=(payload.get("short_description") or "")[:120],
        description=payload.get("description"),
        phone_business=payload.get("phone_business"),
        address=address,
        geo_lat=payload.get("geo_lat"),
        geo_lng=payload.get("geo_lng"),
        instagram=payload.get("instagram"),
        is_24h=bool(payload.get("is_24h", False)),
        status=BusinessStatus(status_value),
    )
    session.add(business)
    await session.flush()
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
    return {"data": _admin_business_payload(business, owner)}


@router.get("/businesses/{business_id}")
async def get_admin_business(
    business_id: str,
    actor: User = Depends(require_permissions("business.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    business = await _get_admin_business(session, business_id)
    owner = await session.get(User, business.owner_id)
    return {"data": _admin_business_payload(business, owner)}


@router.patch("/businesses/{business_id}")
async def update_admin_business(
    business_id: str,
    payload: dict,
    request: Request,
    actor: User = Depends(require_permissions("business.update")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.business import BusinessStatus

    business = await _get_admin_business(session, business_id)
    editable = (
        "name",
        "short_description",
        "description",
        "phone_business",
        "address",
        "geo_lat",
        "geo_lng",
        "instagram",
        "is_24h",
        "is_verified",
        "category_id",
        "subcategory_id",
        "rejection_reason",
    )
    before = {"status": business.status.value, "name": business.name}
    previous_status = business.status
    for field in editable:
        if field in payload:
            setattr(business, field, payload[field])
    if "status" in payload:
        if payload["status"] not in [item.value for item in BusinessStatus]:
            raise AppError("validation_error", "invalid_status", 422)
        business.status = BusinessStatus(payload["status"])
        if business.status != BusinessStatus.REJECTED and "rejection_reason" not in payload:
            business.rejection_reason = None
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
    return {"data": _admin_business_payload(business, owner)}


@router.delete("/businesses/{business_id}")
async def delete_admin_business(
    business_id: str,
    request: Request,
    actor: User = Depends(require_permissions("business.delete")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import datetime, timezone

    business = await _get_admin_business(session, business_id)
    business.deleted_at = datetime.now(timezone.utc)
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
) -> dict:
    del actor  # superadmin gate already enforced via dependency
    result = await session.execute(
        select(User).where(User.deleted_at.is_(None)).order_by(User.created_at)
    )
    users = list(result.scalars().all())
    return {"data": {"items": [_to_admin_response(u) for u in users]}}


@router.post("/users")
async def create_admin(
    payload: dict,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    phone = security.normalize_phone(payload.get("phone", ""))
    existing = (
        await session.execute(select(User).where(User.phone == phone))
    ).scalars().first()
    if existing is not None:
        raise AppError("conflict", "user_already_exists", 409, {"phone": phone})
    permissions = validate_permission_codes(payload.get("permissions") or [])
    user = User(
        phone=phone,
        full_name=(payload.get("full_name") or "").strip() or None,
        role=UserRole.ADMIN,
        permissions=permissions,
        is_phone_verified=True,
    )
    session.add(user)
    await session.flush()
    await _write_audit(
        session,
        actor_id=actor.id,
        action="admin.user.created",
        entity_type="user",
        entity_id=str(user.id),
        after={"role": "admin", "permissions": permissions},
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(user)
    return {"data": _to_admin_response(user)}


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
