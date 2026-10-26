from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.deps import get_current_user, get_otp_service, require_permissions, require_superadmin
from app.core.errors import AppError
from app.core.permissions import permission_catalog, validate_permission_codes
from app.db.session import get_db
from app.models.admin import AuditLog
from app.models.user import User, UserRole
from app.schemas.admin import AdminUserResponse, AdminUserUpdate
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


@router.get("/me")
async def admin_me(user: User = Depends(get_current_user)) -> dict:
    return {"data": {"user": _to_admin_response(user), "is_superadmin": user.role == UserRole.SUPERADMIN}}


@router.get("/businesses")
async def list_admin_businesses(
    status: Optional[str] = None,
    actor: User = Depends(require_permissions("business.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    from app.models.business import Business

    stmt = select(Business).where(Business.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Business.status == status)
    rows = (await session.execute(stmt.order_by(Business.created_at.desc()).limit(100))).scalars().all()
    return {"data": {"items": [
        {
            "id": str(b.id),
            "name": b.name,
            "slug": b.slug,
            "status": b.status.value if hasattr(b.status, "value") else str(b.status),
            "is_verified": b.is_verified,
            "is_24h": b.is_24h,
            "owner_id": str(b.owner_id),
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in rows
    ]}}


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
    business.status = BusinessStatus.APPROVED
    business.rejection_reason = None
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
    business.status = BusinessStatus.REJECTED
    business.rejection_reason = payload.get("reason")
    await _write_audit(session, actor.id, "business.reject", "business", str(bid), after={"reason": business.rejection_reason})
    await session.commit()
    return {"data": {"id": str(bid), "status": "rejected"}}


@router.get("/reviews")
async def list_admin_reviews(
    status: Optional[str] = None,
    actor: User = Depends(require_permissions("review.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    from app.models.review import Review

    stmt = select(Review).where(Review.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Review.status == status)
    rows = (await session.execute(stmt.order_by(Review.created_at.desc()).limit(100))).scalars().all()
    return {"data": {"items": [
        {"id": str(r.id), "business_id": str(r.business_id), "rating": r.rating,
         "text": r.text, "status": r.status}
        for r in rows
    ]}}


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
