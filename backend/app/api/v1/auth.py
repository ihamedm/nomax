import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.deps import client_ip, get_current_user, get_otp_service
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    OtpRequest,
    OtpVerify,
    PasswordLogin,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.services.auth_service import (
    authenticate_user,
    ensure_not_blocked,
    forgot_password,
    issue_tokens,
    login_with_password,
    logout_session,
    rate_limit,
    refresh_session,
    register_user,
    reset_password,
)
from app.services.otp_service import OtpService

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)


def _user_response(user: User) -> UserResponse:
    return UserResponse(
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
    )


async def _login_payload(user: User) -> dict:
    access_token, refresh_token = await issue_tokens(user)
    return {
        "access": access_token,
        "refresh": refresh_token,
        "user": _user_response(user).model_dump(mode="json"),
    }


async def _load_user(session: AsyncSession, phone: str) -> User | None:
    result = await session.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user is not None and user.deleted_at is not None:
        raise AppError("account_disabled", "account_disabled", 403)
    return user


@router.post("/otp/request")
async def otp_request(
    payload: OtpRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    otp_service: OtpService = Depends(get_otp_service),
) -> dict:
    phone = security.normalize_phone(payload.phone)
    ip = client_ip(request)
    await ensure_not_blocked(otp_service.redis, phone=phone, ip=ip)
    code = await otp_service.issue(phone, ip=ip, session=session)
    if code is None:
        return {"data": {"status": "sent"}}
    if settings.APP_ENV == "production":
        # The console provider is a development fallback. Returning the code
        # here would let anyone log in as any phone number, so never expose it
        # in production: the operator reads it from Redis instead.
        logger.warning(
            "SMS_PROVIDER=console in production; OTP for %s was not returned to the client",
            phone,
        )
        return {"data": {"status": "sent"}}
    return {"data": {"status": "issued", "dev_otp": code, "expires_in": settings.OTP_TTL_SECONDS}}


@router.post("/otp/verify")
async def otp_verify(
    payload: OtpVerify,
    session: AsyncSession = Depends(get_db),
    otp_service: OtpService = Depends(get_otp_service),
) -> dict:
    phone = security.normalize_phone(payload.phone)
    user = await _load_user(session, phone)
    user = await authenticate_user(session, otp_service, phone, payload.code, payload.national_id, existing=user)
    return {"data": await _login_payload(user)}


@router.post("/check")
async def check_phone(
    payload: OtpRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
) -> dict:
    phone = security.normalize_phone(payload.phone)
    await ensure_not_blocked(redis, phone=phone, ip=client_ip(request))
    # A cheap DB lookup, but the answer separates users from strangers, so keep
    # a per-IP cap against enumeration.
    await rate_limit(redis, f"auth:chkrl:ip:{client_ip(request)}", settings.CHECK_RATE_LIMIT_PER_HOUR)
    result = await session.execute(select(User.id).where(User.phone == phone, User.deleted_at.is_(None)))
    return {"data": {"registered": result.scalar_one_or_none() is not None}}


@router.post("/login")
async def password_login(
    payload: PasswordLogin,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
) -> dict:
    phone = security.normalize_phone(payload.phone)
    await rate_limit(redis, f"auth:loginrl:ip:{client_ip(request)}", settings.LOGIN_RATE_LIMIT_PER_HOUR)
    user = await login_with_password(session, redis, phone, payload.password, client_ip(request))
    return {"data": await _login_payload(user)}


@router.post("/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
) -> dict:
    phone = security.normalize_phone(payload.phone)
    user = await register_user(
        session,
        redis,
        phone,
        client_ip(request),
        payload.full_name.strip(),
        payload.national_id.strip(),
        payload.password,
    )
    return {"data": await _login_payload(user)}


@router.post("/forgot-password")
async def forgot(
    payload: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    otp_service: OtpService = Depends(get_otp_service),
) -> dict:
    phone = security.normalize_phone(payload.phone)
    code = await forgot_password(session, otp_service, phone, client_ip(request))
    if code is None or settings.APP_ENV == "production":
        if code is not None:
            logger.warning(
                "SMS_PROVIDER=console in production; reset OTP for %s was not returned to the client",
                phone,
            )
        return {"data": {"status": "sent"}}
    return {"data": {"status": "issued", "dev_otp": code, "expires_in": settings.OTP_TTL_SECONDS}}


@router.post("/reset-password")
async def reset(
    payload: ResetPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    otp_service: OtpService = Depends(get_otp_service),
    redis = Depends(get_redis),
) -> dict:
    phone = security.normalize_phone(payload.phone)
    user = await reset_password(
        session, otp_service, redis, phone, payload.code, payload.password, client_ip(request)
    )
    return {"data": await _login_payload(user)}


@router.post("/refresh")
async def refresh(refresh_token: RefreshRequest, redis = Depends(get_redis)) -> dict:
    access_token, new_refresh = await refresh_session(redis, refresh_token.refresh)
    return {"data": {"access": access_token, "refresh": new_refresh}}


@router.post("/logout")
async def logout(refresh_token: RefreshRequest, redis = Depends(get_redis)) -> dict:
    await logout_session(redis, refresh_token.refresh)
    return {"data": {"status": "ok"}}


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict:
    return {"data": _user_response(user).model_dump(mode="json")}
