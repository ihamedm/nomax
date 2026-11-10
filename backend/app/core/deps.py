import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.errors import AppError
from app.core.permissions import has_permission
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.auth_service import ensure_not_blocked, is_token_revoked
from app.services.otp_service import OtpService
from app.services.sms_provider import get_sms_provider


bearer_scheme = HTTPBearer(auto_error=False)


def client_ip(request: Request) -> str:
    """Real client IP; the app sits behind a proxy in production."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> User:
    if bearer is None or not bearer.credentials or bearer.scheme.lower() != "bearer":
        raise AppError("auth_unauthorized", "missing_bearer_token", 401)
    payload = security.decode_access_token(bearer.credentials)
    user_id = uuid.UUID(payload["sub"])
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AppError("auth_unauthorized", "user_not_found", 401)
    if await is_token_revoked(redis, str(user.id), payload.get("iat")):
        raise AppError("token_revoked", "token_revoked", 401)
    await ensure_not_blocked(redis, phone=user.phone, ip=client_ip(request))
    return user


async def get_optional_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> User | None:
    """Resolve a bearer token when present, without requiring authentication."""
    if bearer is None or not bearer.credentials or bearer.scheme.lower() != "bearer":
        return None
    try:
        payload = security.decode_access_token(bearer.credentials)
        user_id = uuid.UUID(payload["sub"])
        user = await session.get(User, user_id)
        if user is None or user.deleted_at is not None:
            return None
        if await is_token_revoked(redis, str(user.id), payload.get("iat")):
            return None
        await ensure_not_blocked(redis, phone=user.phone, ip=client_ip(request))
    except (AppError, KeyError, ValueError):
        return None
    return user


def require_permissions(*codes: str):
    async def _require(user: User = Depends(get_current_user)) -> User:
        for code in codes:
            if not has_permission(user, code):
                raise AppError("forbidden", "permission_denied", 403, {"permission": code})
        return user

    return _require


def require_superadmin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.SUPERADMIN:
        raise AppError("forbidden", "superadmin_required", 403)
    return user


def get_otp_service(redis=Depends(get_redis)) -> OtpService:
    return OtpService(redis, get_sms_provider())
