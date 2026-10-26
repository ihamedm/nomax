from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.deps import get_current_user, get_otp_service
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import OtpRequest, OtpVerify, RefreshRequest, UserResponse
from app.services.auth_service import authenticate_user, issue_tokens, logout_session, refresh_session
from app.services.otp_service import OtpService
from app.services.sms_provider import get_sms_provider

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/otp/request")
async def otp_request(payload: OtpRequest, request: Request, otp_service: OtpService = Depends(get_otp_service)) -> dict:
    phone = security.normalize_phone(payload.phone)
    client_ip = _client_ip(request)
    code = await otp_service.issue(phone, ip=client_ip)
    if code is None:
        return {"data": {"status": "sent"}}
    return {"data": {"status": "issued", "dev_otp": code, "expires_in": settings.OTP_TTL_SECONDS}}


@router.post("/otp/verify")
async def otp_verify(
    payload: OtpVerify,
    session: AsyncSession = Depends(get_db),
    otp_service: OtpService = Depends(get_otp_service),
) -> dict:
    phone = security.normalize_phone(payload.phone)
    user = await authenticate_user(session, otp_service, phone, payload.code, payload.national_id)
    access_token, refresh_token = await issue_tokens(user)
    return {
        "data": {
            "access": access_token,
            "refresh": refresh_token,
            "user": UserResponse(
                id=str(user.id),
                phone=user.phone,
                national_id=user.national_id,
                full_name=user.full_name,
                role=user.role.value,
                permissions=list(user.permissions or []),
                is_phone_verified=user.is_phone_verified,
                is_national_id_verified=user.is_national_id_verified,
                last_login_at=user.last_login_at,
                created_at=user.created_at,
            ).model_dump(mode="json"),
        }
    }


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
    return {
        "data": UserResponse(
            id=str(user.id),
            phone=user.phone,
            national_id=user.national_id,
            full_name=user.full_name,
            role=user.role.value,
            permissions=list(user.permissions or []),
            is_phone_verified=user.is_phone_verified,
            is_national_id_verified=user.is_national_id_verified,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        ).model_dump(mode="json"),
    }
