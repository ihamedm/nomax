from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import select

from app.core import security
from app.core.config import settings
from app.core.errors import AppError
from app.models.user import User, UserRole
from app.services.otp_service import OtpService
from app.services.shahkar_service import verify_mobile_owner


def _now() -> datetime:
    return datetime.now(timezone.utc)


_PW_ATTEMPTS_PREFIX = "auth:pwatt:{phone}"
_PW_BLOCK_PREFIX = "auth:pwblock:{phone}"


async def rate_limit(redis: Redis, key: str, limit: int, window_seconds: int = 3600) -> int:
    """Sliding-in-window counter; raises 429 once `limit` is exceeded."""
    if limit <= 0:
        return 0
    count = await redis.incr(key)
    ttl = await redis.ttl(key)
    if ttl < 0:
        await redis.expire(key, window_seconds)
        ttl = window_seconds
    if count > limit:
        raise AppError(
            "rate_limited",
            "rate_limited",
            429,
            {"retry_after_seconds": max(ttl, 0)},
        )
    return count


async def _password_lockout_check(redis: Redis, phone: str) -> None:
    ttl = await redis.ttl(_PW_BLOCK_PREFIX.format(phone=phone))
    if ttl > 0:
        raise AppError(
            "auth_blocked",
            "too_many_failed_logins",
            429,
            {"retry_after_seconds": ttl},
        )


async def _password_failure(redis: Redis, phone: str) -> None:
    key = _PW_ATTEMPTS_PREFIX.format(phone=phone)
    attempts = await redis.incr(key)
    if attempts == 1:
        await redis.expire(key, 3600)
    if attempts >= settings.PASSWORD_MAX_ATTEMPTS:
        # Block the phone outright: bots iterating passwords must not keep the
        # counter alive forever. SET (not EXPIRE) because the key may not exist yet.
        await redis.delete(key)
        await redis.set(_PW_BLOCK_PREFIX.format(phone=phone), "1", ex=settings.PASSWORD_BLOCK_SECONDS)


async def login_with_password(session, redis: Redis, phone: str, password: str) -> User:
    await _password_lockout_check(redis, phone)
    result = await session.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user is not None and user.deleted_at is not None:
        raise AppError("account_disabled", "account_disabled", 403)
    if user is None or not user.hashed_password:
        # Users created before passwords existed: point them at reset, don't
        # count the attempt (there is nothing to brute-force).
        raise AppError("password_not_set", "password_not_set", 403)
    if not security.verify_password(password, user.hashed_password):
        await _password_failure(redis, phone)
        raise AppError("invalid_credentials", "invalid_credentials", 401)
    await redis.delete(_PW_ATTEMPTS_PREFIX.format(phone=phone))
    user.is_verified = True
    user.last_login_at = _now()
    return user


async def register_user(
    session,
    redis: Redis,
    phone: str,
    ip: str,
    full_name: str,
    national_id: str,
    password: str,
) -> User:
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise AppError("password_too_short", "password_too_short", 422, {"min_length": settings.PASSWORD_MIN_LENGTH})
    if not security.validate_iranian_national_id(national_id):
        raise AppError("invalid_national_id", "invalid_national_id", 422, {"national_id": national_id})

    existing = await session.execute(select(User).where(User.phone == phone))
    user = existing.scalar_one_or_none()
    if user is not None and user.deleted_at is None:
        raise AppError("phone_already_registered", "phone_already_registered", 409)
    if user is not None and user.deleted_at is not None:
        raise AppError("account_disabled", "account_disabled", 403)

    in_use = await session.execute(
        select(User.id).where(User.national_id == national_id)
    )
    if in_use.scalar_one_or_none() is not None:
        raise AppError("conflict", "national_id_in_use", 409)

    # Each registration spends a metered Shahkar inquiry, so cap per IP. Only
    # count requests that reach the provider: local validation mistakes should
    # not burn the caller's hourly budget.
    await rate_limit(redis, f"auth:regrl:ip:{ip}", settings.REGISTER_RATE_LIMIT_PER_HOUR)

    # Shahkar raises a descriptive AppError when the SIM belongs to someone else.
    await verify_mobile_owner(national_id, phone)

    user = User(
        phone=phone,
        role=UserRole.CUSTOMER,
        permissions=[],
        full_name=full_name,
        national_id=national_id,
        hashed_password=security.hash_password(password),
    )
    # Shahkar match proves SIM ownership, so mark the account as trusted.
    user.is_verified = True
    user.is_phone_verified = True
    user.is_national_id_verified = True
    user.national_id_verified_at = _now()
    user.last_login_at = _now()
    session.add(user)
    await session.flush()
    return user


async def forgot_password(session, otp_service: OtpService, phone: str, ip: str) -> str | None:
    """Issue a password-reset OTP; silent about whether the phone is registered."""
    result = await session.execute(select(User.id).where(User.phone == phone, User.deleted_at.is_(None)))
    if result.scalar_one_or_none() is None:
        return None
    return await otp_service.issue(phone, ip=ip, session=session, purpose="password_reset")


async def reset_password(session, otp_service: OtpService, redis: Redis, phone: str, code: str, password: str) -> User:
    if not await otp_service.verify(phone, code):
        raise AppError("otp_invalid", "invalid_or_expired_otp_code", 401)
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise AppError("validation_error", "password_too_short", 422, {"min_length": settings.PASSWORD_MIN_LENGTH})

    result = await session.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        raise AppError("account_disabled", "account_disabled", 403)

    user.hashed_password = security.hash_password(password)
    user.is_verified = True
    user.is_phone_verified = True
    user.last_login_at = _now()
    await redis.delete(_PW_BLOCK_PREFIX.format(phone=phone))
    await redis.delete(_PW_ATTEMPTS_PREFIX.format(phone=phone))
    return user


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
    existing: User | None = None,
) -> User:
    if not await otp_service.verify(phone, code):
        raise AppError("otp_invalid", "invalid_or_expired_otp_code", 401)

    user = existing
    if user is None:
        result = await session.execute(select(User).where(User.phone == phone))
        user = result.scalar_one_or_none()
        if user is not None and user.deleted_at is not None:
            raise AppError("account_disabled", "account_disabled", 403)
    if user is None:
        user = User(phone=phone, role=UserRole.CUSTOMER, permissions=[])
        session.add(user)
        await session.flush()

    user.is_verified = True
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
