import logging
import random

from app.core import security
from app.core.config import settings
from app.core.errors import AppError
from app.models.sms import SmsLog, SmsStatus
from app.services.sms_provider import SmsProvider

logger = logging.getLogger(__name__)

OTP_HASH_PREFIX = "otp:{phone}"
DEV_OTP_PREFIX = "dev:otp:{phone}"


class OtpService:
    def __init__(self, redis, sms_provider: SmsProvider) -> None:
        self.redis = redis
        self.sms_provider = sms_provider

    @property
    def use_dev_otp(self) -> bool:
        return settings.SMS_PROVIDER == "console" or settings.APP_ENV in ("local", "test")

    async def _rate_check(self, key: str) -> int:
        # A non-positive limit disables OTP request throttling (development).
        if settings.OTP_RATE_LIMIT_PER_HOUR <= 0:
            return 0
        count = await self.redis.incr(key)
        ttl = await self.redis.ttl(key)
        if ttl < 0:
            ttl = settings.OTP_RATE_LIMIT_PER_HOUR * 3600
            await self.redis.expire(key, ttl)
        if count > settings.OTP_RATE_LIMIT_PER_HOUR:
            raise AppError(
                "otp_rate_limited",
                "too_many_otp_requests",
                429,
                {"retry_after_seconds": max(ttl, 0)},
            )
        return count

    async def _log_attempt(self, session, phone: str, result) -> None:
        if session is None:
            return
        session.add(
            SmsLog(
                phone=phone,
                purpose="otp",
                provider=self.sms_provider.name,
                provider_message_id=result.provider_message_id,
                status=SmsStatus.SENT if result.success else SmsStatus.FAILED,
                error=result.error,
            )
        )
        await session.flush()

    async def issue(self, phone: str, ip: str, session=None) -> str | None:
        await self._rate_check(f"otp:rl:phone:{phone}")
        await self._rate_check(f"otp:rl:ip:{ip}")

        code = f"{random.randint(100000, 999999)}"

        if self.use_dev_otp:
            await self.redis.set(DEV_OTP_PREFIX.format(phone=phone), code, ex=settings.OTP_TTL_SECONDS)
            return code

        key = OTP_HASH_PREFIX.format(phone=phone)
        await self.redis.set(key, security.hash_otp(code), ex=settings.OTP_TTL_SECONDS)

        result = await self.sms_provider.send(phone, code)
        await self._log_attempt(session, phone, result)

        if not result.success:
            # Do not leave a valid-but-undelivered code behind.
            await self.redis.delete(key)
            logger.warning("SMS delivery failed for %s: %s", phone, result.error)
            # Persist the audit row even though the request will fail and the
            # dependency teardown will roll the request transaction back.
            if session is not None:
                await session.commit()
            raise AppError("sms_provider_unavailable", "sms_provider_unavailable", 503)

        return None

    async def verify(self, phone: str, code: str) -> bool:
        key = DEV_OTP_PREFIX.format(phone=phone) if self.use_dev_otp else OTP_HASH_PREFIX.format(phone=phone)
        raw = await self.redis.get(key)
        if not raw:
            return False

        attempts_key = f"otp:att:{phone}"
        attempts = await self.redis.incr(attempts_key)
        if attempts == 1:
            # Set the window once; later attempts must not extend it.
            await self.redis.expire(attempts_key, settings.OTP_TTL_SECONDS)
        if attempts > settings.OTP_MAX_ATTEMPTS:
            # Burn the code so an attacker cannot keep guessing after the cap.
            await self.redis.delete(key)
            return False

        if not security.verify_otp_value(code, raw):
            return False
        await self.redis.delete(key)
        await self.redis.delete(attempts_key)
        return True

    async def issue_dev_otp(self, phone: str) -> str:
        code = f"{random.randint(100000, 999999)}"
        await self.redis.set(DEV_OTP_PREFIX.format(phone=phone), code, ex=settings.OTP_TTL_SECONDS)
        return code

    async def get_dev_otp(self, phone: str) -> str | None:
        return await self.redis.get(DEV_OTP_PREFIX.format(phone=phone))

    async def list_dev_otps(self) -> list[tuple[str, str, int]]:
        """Return (phone, code, ttl_seconds) for every live dev OTP."""
        items: list[tuple[str, str, int]] = []
        async for key in self.redis.scan_iter(match="dev:otp:*"):
            code = await self.redis.get(key)
            if code is None:
                continue
            phone = key.rsplit(":", 1)[-1]
            ttl = await self.redis.ttl(key)
            items.append((phone, code, int(ttl)))
        items.sort(key=lambda item: item[0])
        return items
