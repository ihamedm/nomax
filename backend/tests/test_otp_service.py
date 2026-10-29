import pytest

from app.core import security
from app.core.config import settings
from app.core.errors import AppError
from app.services.otp_service import OtpService
from app.services.sms_provider import ConsoleSmsProvider


@pytest.fixture
async def otp_service(fake_redis):
    return OtpService(fake_redis, ConsoleSmsProvider())


@pytest.fixture
def console_sms():
    from app.services.sms_provider import ConsoleSmsProvider

    return ConsoleSmsProvider()


@pytest.mark.asyncio
async def test_dev_otp_issue_and_verify(otp_service):
    code = await otp_service.issue("09123456789", ip="1.2.3.4")
    assert isinstance(code, str)
    assert len(code) == 6
    assert await otp_service.verify("09123456789", code) is True
    # single use
    assert await otp_service.verify("09123456789", code) is False


@pytest.mark.asyncio
async def test_dev_otp_requires_valid_code(otp_service):
    await otp_service.issue_dev_otp("09123456789")
    stored = await otp_service.get_dev_otp("09123456789")
    assert stored is not None
    assert await otp_service.verify("09123456789", "000000") is False
    assert await otp_service.verify("09123456789", stored) is True


@pytest.mark.asyncio
async def test_otp_rate_limit_exceeded(otp_service, monkeypatch):
    monkeypatch.setattr(settings, "OTP_RATE_LIMIT_PER_HOUR", 2)
    first = await otp_service.issue("09123456789", ip="1.2.3.4")
    second = await otp_service.issue("09123456789", ip="1.2.3.4")
    assert isinstance(first, str) and isinstance(second, str)
    with pytest.raises(AppError) as exc_info:
        await otp_service.issue("09123456789", ip="1.2.3.4")
    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "otp_rate_limited"


@pytest.mark.asyncio
async def test_otp_rate_limit_can_be_disabled(otp_service, monkeypatch):
    monkeypatch.setattr(settings, "OTP_RATE_LIMIT_PER_HOUR", 0)
    for _ in range(5):
        assert isinstance(await otp_service.issue("09123456789", ip="1.2.3.4"), str)
