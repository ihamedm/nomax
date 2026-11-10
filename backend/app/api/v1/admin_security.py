"""Admin security: inspect/reset auth throttles, block phones/IPs, force logout.

Throttle keys are written by the auth and OTP services; this router only reads
and deletes the known prefixes, so an operator can never target arbitrary Redis
keys from the dashboard.
"""

from ipaddress import ip_address

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import _write_audit
from app.core import security
from app.core.deps import require_superadmin
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.services import auth_service

router = APIRouter(prefix="/admin/security", tags=["admin-security"])

RATE_LIMIT_KINDS = {
    "register_ip": "auth:regrl:ip:",
    "check_ip": "auth:chkrl:ip:",
    "login_ip": "auth:loginrl:ip:",
    "password_attempts": "auth:pwatt:",
    "password_block": "auth:pwblock:",
    "otp_phone": "otp:rl:phone:",
    "otp_ip": "otp:rl:ip:",
    "otp_attempts": "otp:att:",
}
BLOCK_PREFIXES = {"phone": "auth:block:phone:", "ip": "auth:block:ip:"}


class ResetKeyBody(BaseModel):
    key: str


class ResetAllBody(BaseModel):
    kind: str | None = None


class BlockBody(BaseModel):
    kind: str
    value: str


class LogoutBody(BaseModel):
    phone: str


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _ttl(value: int) -> int | None:
    """Permanent keys (no expiry) come back from Redis as -1."""
    return value if value >= 0 else None


def _normalize_phone(value: str) -> str:
    return security.normalize_phone(value)


def _normalize_ip(value: str) -> str:
    try:
        return str(ip_address(value.strip()))
    except ValueError:
        raise AppError("validation_error", "invalid_ip", 422, {"ip": value}) from None


def _normalize_block(kind: str, value: str) -> str:
    if kind == "phone":
        return _normalize_phone(value)
    if kind == "ip":
        return _normalize_ip(value)
    raise AppError("validation_error", "invalid_block_kind", 422, {"kind": kind})


async def _scan(redis, prefix: str) -> list[tuple[str, int, int]]:
    entries: list[tuple[str, int, int]] = []
    async for key in redis.scan_iter(match=f"{prefix}*"):
        entries.append((key[len(prefix) :], _as_int(await redis.get(key)), await redis.ttl(key)))
    return entries


async def _rate_limits(redis) -> list[dict]:
    items: list[dict] = []
    for kind, prefix in RATE_LIMIT_KINDS.items():
        for subject, count, ttl in await _scan(redis, prefix):
            items.append(
                {
                    "key": f"{prefix}{subject}",
                    "kind": kind,
                    "subject": subject,
                    "count": count,
                    "ttl_seconds": _ttl(ttl),
                }
            )
    items.sort(key=lambda item: (item["kind"], item["subject"]))
    return items


async def _blocks(redis) -> list[dict]:
    items: list[dict] = []
    for kind, prefix in BLOCK_PREFIXES.items():
        for subject, _value, ttl in await _scan(redis, prefix):
            items.append({"kind": kind, "subject": subject, "ttl_seconds": _ttl(ttl)})
    items.sort(key=lambda item: (item["kind"], item["subject"]))
    return items


async def _audit(session, actor, request, action: str, entity_type: str, entity_id, after: dict) -> None:
    await _write_audit(
        session,
        actor_id=actor.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        after=after,
        ip=request.client.host if request.client else None,
    )
    await session.commit()


@router.get("")
async def get_security(
    actor: User = Depends(require_superadmin),
    redis=Depends(get_redis),
) -> dict:
    del actor
    return {"data": {"rate_limits": await _rate_limits(redis), "blocks": await _blocks(redis)}}


@router.post("/rate-limits/reset")
async def reset_rate_limit(
    payload: ResetKeyBody,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    if not any(payload.key.startswith(prefix) for prefix in RATE_LIMIT_KINDS.values()):
        raise AppError("validation_error", "invalid_rate_limit_key", 422, {"key": payload.key})
    await redis.delete(payload.key)
    await _audit(session, actor, request, "admin.security.reset", "rate_limit", payload.key, {"key": payload.key})
    return {"data": {"key": payload.key, "reset": True}}


@router.post("/rate-limits/reset-all")
async def reset_all_rate_limits(
    payload: ResetAllBody,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    if payload.kind is not None and payload.kind not in RATE_LIMIT_KINDS:
        raise AppError("validation_error", "invalid_rate_limit_kind", 422, {"kind": payload.kind})
    prefixes = (
        [RATE_LIMIT_KINDS[payload.kind]] if payload.kind else list(RATE_LIMIT_KINDS.values())
    )
    deleted = 0
    for prefix in prefixes:
        async for key in redis.scan_iter(match=f"{prefix}*"):
            deleted += await redis.delete(key)
    await _audit(
        session,
        actor,
        request,
        "admin.security.reset_all",
        "rate_limit",
        payload.kind or "all",
        {"kind": payload.kind, "deleted": deleted},
    )
    return {"data": {"deleted": deleted}}


@router.post("/blocks")
async def block(
    payload: BlockBody,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    subject = _normalize_block(payload.kind, payload.value)
    key = f"{BLOCK_PREFIXES[payload.kind]}{subject}"
    await redis.set(key, "1")
    await _audit(
        session,
        actor,
        request,
        "admin.security.block",
        payload.kind,
        subject,
        {"kind": payload.kind, "subject": subject},
    )
    return {"data": {"kind": payload.kind, "subject": subject, "blocked": True}}


@router.delete("/blocks/{kind}/{value}")
async def unblock(
    kind: str,
    value: str,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    subject = _normalize_block(kind, value)
    await redis.delete(f"{BLOCK_PREFIXES[kind]}{subject}")
    await _audit(
        session,
        actor,
        request,
        "admin.security.unblock",
        kind,
        subject,
        {"kind": kind, "subject": subject},
    )
    return {"data": {"kind": kind, "subject": subject, "blocked": False}}


@router.post("/users/logout")
async def force_logout(
    payload: LogoutBody,
    request: Request,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    phone = _normalize_phone(payload.phone)
    user = (await session.execute(select(User).where(User.phone == phone))).scalars().first()
    if user is None:
        raise AppError("not_found", "user_not_found", 404, {"phone": phone})
    if user.id == actor.id:
        raise AppError("validation_error", "cannot_logout_self", 422)

    await auth_service.force_logout(redis, user.id)
    await _audit(
        session,
        actor,
        request,
        "admin.security.force_logout",
        "user",
        str(user.id),
        {"phone": phone},
    )
    return {"data": {"id": str(user.id), "phone": user.phone, "full_name": user.full_name}}
