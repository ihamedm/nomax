from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core import security
from app.core.config import settings
from app.core.errors import AppError
from app.models.user import User, UserRole
from app.services.otp_service import OtpService


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def issue_tokens(user: User) -> tuple[str, str]:
    access_token = security.create_access_token(user.id, user.role.value)
    refresh_token, _jti, _fam = security.create_refresh_token(user.id, user.role.value)
    return access_token, refresh_token


async def authenticate_user(
    session,
    otp_service: OtpService,
    phone: str,
    code: str,
    national_id: str | None = None,
) -> User:
    if not await otp_service.verify(phone, code):
        raise AppError("otp_invalid", "invalid_or_expired_otp_code", 401)

    result = await session.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user is not None and user.deleted_at is not None:
        raise AppError("account_disabled", "account_disabled", 403)
    if user is None:
        user = User(phone=phone, role=UserRole.CUSTOMER, permissions=[])
        session.add(user)
        await session.flush()

    user.is_phone_verified = True
    user.last_login_at = _now()
    if national_id:
        if not security.validate_iranian_national_id(national_id):
            raise AppError("validation_error", "invalid_national_id", 422, {"national_id": national_id})
        if user.national_id and user.national_id != national_id:
            raise AppError("conflict", "national_id_already_set", 409)
        in_use = await session.execute(
            select(User.id).where(User.national_id == national_id, User.id != user.id)
        )
        if in_use.scalar_one_or_none() is not None:
            raise AppError("conflict", "national_id_in_use", 409)
        user.national_id = national_id
        user.is_national_id_verified = True
        user.national_id_verified_at = _now()

    return user


async def refresh_session(redis, refresh_token: str) -> tuple[str, str]:
    payload = security.decode_refresh_token(refresh_token)
    jti = payload.get("jti")
    fam = payload.get("fam")
    user_id = payload.get("sub")
    role = payload.get("role")

    family_key = f"auth:fam:{fam}"
    refresh_ttl_seconds = int(timedelta(days=settings.JWT_REFRESH_TTL_DAYS).total_seconds())
    if await redis.get(f"auth:famrev:{fam}"):
        raise AppError("token_revoked", "refresh_token_revoked", 401)

    # sadd is atomic: a second concurrent use of the same jti gets 0 and is treated as replay.
    if not await redis.sadd(family_key, jti):
        await redis.set(f"auth:famrev:{fam}", "1", ex=refresh_ttl_seconds)
        await redis.delete(family_key)
        raise AppError("token_revoked", "refresh_token_revoked", 401)

    await redis.expire(family_key, refresh_ttl_seconds)

    new_refresh, _new_jti, _new_fam = security.create_refresh_token(user_id, role, family_id=fam)
    access_token = security.create_access_token(user_id, role)
    return access_token, new_refresh


async def logout_session(redis, refresh_token: str) -> None:
    payload = security.decode_refresh_token(refresh_token)
    fam = payload.get("fam")
    if not await redis.get(f"auth:famrev:{fam}"):
        await redis.set(f"auth:famrev:{fam}", "1", ex=int(timedelta(days=settings.JWT_REFRESH_TTL_DAYS).total_seconds()))
        await redis.delete(f"auth:fam:{fam}")
