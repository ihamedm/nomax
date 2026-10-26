from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.deps import get_current_user, get_otp_service, require_superadmin
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
    result = await session.execute(select(User))
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
    before = {"role": target.role.value, "permissions": list(target.permissions or [])}
    if payload.role is not None:
        target.role = payload.role
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
