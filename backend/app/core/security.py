import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.errors import AppError

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

_OTP_HASH_KEY = "nomax-otp-hmac-v1"


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------


def hash_otp(value: str) -> str:
    digest = hmac.new(_OTP_HASH_KEY.encode("utf-8"), value.strip().encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def verify_otp(plain: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_otp(plain), hashed)


def verify_otp_value(plain: str, stored: str) -> bool:
    """Accept either a plain OTP value (dev mirror) or a hex hash (production)."""
    plain_norm = plain.strip()
    stored_norm = stored.strip()
    if len(stored_norm) == 64 and all(c in "0123456789abcdef" for c in stored_norm):
        return hmac.compare_digest(hash_otp(plain_norm), stored_norm)
    return hmac.compare_digest(plain_norm, stored_norm)


# ---------------------------------------------------------------------------
# Passwords (escape hatch for bootstrap accounts; OTP remains primary auth)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT access tokens
# ---------------------------------------------------------------------------


def _encode_jwt(claims: dict, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = dict(claims)
    payload.setdefault("iat", int(now.timestamp()))
    payload.setdefault("exp", int((now + expires_delta).timestamp()))
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_access_token(user_id, role: str) -> str:
    return _encode_jwt(
        {"sub": str(user_id), "role": role, "typ": "access"},
        timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES),
    )


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AppError("token_invalid", "invalid_token", 401) from exc
    if payload.get("typ") != "access":
        raise AppError("token_invalid", "invalid_token", 401)
    return payload


# ---------------------------------------------------------------------------
# JWT refresh tokens with rotation + reuse (theft) detection
# ---------------------------------------------------------------------------


def create_refresh_token(user_id, role: str, family_id: str | None = None) -> tuple[str, str, str]:
    now = datetime.now(timezone.utc)
    family_id = family_id or uuid.uuid4().hex
    jti = uuid.uuid4().hex
    claims = {
        "sub": str(user_id),
        "role": role,
        "fam": family_id,
        "jti": jti,
        "typ": "refresh",
    }
    token = jwt.encode(claims, settings.JWT_SECRET, algorithm="HS256")
    return token, jti, family_id


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AppError("token_invalid", "invalid_token", 401) from exc
    if payload.get("typ") != "refresh":
        raise AppError("token_invalid", "invalid_token", 401)
    return payload


# ---------------------------------------------------------------------------
# Iranian national ID checksum
# ---------------------------------------------------------------------------


def validate_iranian_national_id(nid: str) -> bool:
    if not isinstance(nid, str) or not nid.isdigit() or len(nid) != 10:
        return False
    digits = [int(d) for d in nid]
    checksum = digits[-1]
    weights = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(d * w for d, w in zip(digits[:9], weights))
    remainder = total % 11
    expected = remainder if remainder < 2 else 11 - remainder
    return expected == checksum


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if digits.startswith("98") and len(digits) > 10:
        digits = digits[2:]
    digits = digits.lstrip("0")
    if len(digits) != 10 or not digits.startswith("9") or not digits[1:].isdigit():
        raise AppError("validation_error", "invalid_phone_number", 422, {"phone": str(phone)})
    return digits
