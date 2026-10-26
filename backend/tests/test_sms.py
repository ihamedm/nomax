import json

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import AppError
from app.models.sms import SmsLog, SmsStatus
from app.services.otp_service import OtpService
from app.services.sms_provider import (
    MelipayamakSmsProvider,
    SmsProvider,
    SmsSendResult,
)


class FakeProvider(SmsProvider):
    name = "fake"

    def __init__(self, result: SmsSendResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    async def send(self, phone: str, code: str) -> SmsSendResult:
        self.calls.append((phone, code))
        return self.result


def _use_production_sms(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(settings, "SMS_PROVIDER", "mellipayamak")


@pytest.mark.asyncio
async def test_successful_delivery_is_logged(db_session, fake_redis, monkeypatch):
    _use_production_sms(monkeypatch)
    provider = FakeProvider(SmsSendResult(success=True, provider_message_id="msg-1"))
    service = OtpService(fake_redis, provider)

    code = await service.issue("9123456789", ip="1.2.3.4", session=db_session)

    assert code is None
    assert len(provider.calls) == 1
    logs = (await db_session.execute(select(SmsLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].status == SmsStatus.SENT
    assert logs[0].provider == "fake"
    assert logs[0].provider_message_id == "msg-1"
    assert logs[0].phone == "9123456789"


@pytest.mark.asyncio
async def test_failed_delivery_is_logged_and_returns_503(db_session, fake_redis, monkeypatch):
    _use_production_sms(monkeypatch)
    provider = FakeProvider(SmsSendResult(success=False, error="provider_http_500"))
    service = OtpService(fake_redis, provider)

    with pytest.raises(AppError) as exc_info:
        await service.issue("9123456789", ip="1.2.3.4", session=db_session)

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "sms_provider_unavailable"
    logs = (await db_session.execute(select(SmsLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].status == SmsStatus.FAILED
    assert logs[0].error == "provider_http_500"
    # The undelivered code must not stay valid.
    assert await fake_redis.get("otp:9123456789") is None


@pytest.mark.asyncio
async def test_dev_mode_never_calls_the_provider(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "SMS_PROVIDER", "console")
    provider = FakeProvider(SmsSendResult(success=True))
    service = OtpService(fake_redis, provider)

    code = await service.issue("09123456789", ip="1.2.3.4")
    assert code is not None and len(code) == 6
    assert provider.calls == []


@pytest.mark.asyncio
async def test_melipayamak_retries_transient_failures_and_sends_pattern_payload():
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, json={"RetStatus": 0})
        return httpx.Response(200, json={"RetStatus": 1, "Value": "98765"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = MelipayamakSmsProvider(
            api_url="https://sms.test/pattern",
            username="user",
            password="pass",
            body_id=42,
            max_attempts=2,
            client=client,
        )
        result = await provider.send("9123456789", "123456")
    finally:
        await client.aclose()

    assert result.success is True
    assert result.provider_message_id == "98765"
    assert len(calls) == 2

    payload = json.loads(calls[-1].content)
    assert payload == {
        "username": "user",
        "password": "pass",
        "text": "123456",
        "to": "09123456789",
        "bodyId": 42,
    }


@pytest.mark.asyncio
async def test_melipayamak_does_not_retry_a_4xx_configuration_error():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"RetStatus": 0, "StrRetStatus": "unauthorized"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = MelipayamakSmsProvider(
            api_url="https://sms.test/pattern",
            username="user",
            password="wrong",
            body_id=42,
            max_attempts=3,
            client=client,
        )
        result = await provider.send("9123456789", "123456")
    finally:
        await client.aclose()

    assert result.success is False
    assert result.error == "provider_http_401"
    assert calls == 1
