from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class SmsSendResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None


class SmsProvider:
    async def send(self, phone: str, code: str) -> SmsSendResult:
        raise NotImplementedError


class ConsoleSmsProvider(SmsProvider):
    async def send(self, phone: str, code: str) -> SmsSendResult:
        return SmsSendResult(success=True, provider_message_id=f"console-{phone}")


class MelipayamakSmsProvider(SmsProvider):
    def __init__(self, api_url: str, api_key: str, sender_number: str, template_id: int, client=None) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.sender_number = sender_number
        self.template_id = template_id
        self._client = client

    async def send(self, phone: str, code: str) -> SmsSendResult:
        try:
            if self._client is None:
                import httpx

                self._client = httpx.AsyncClient(timeout=10.0)
            response = await self._client.post(
                self.api_url,
                json={
                    "apiKey": self.api_key,
                    "mobile": [phone],
                    "templateId": self.template_id,
                    "parameters": [str(code)],
                },
            )
            if response.status_code < 200 or response.status_code >= 300:
                return SmsSendResult(success=False, error=f"provider_http_{response.status_code}")
            return SmsSendResult(success=True, provider_message_id=f"mellipayamak-{phone}")
        except Exception as exc:  # noqa: BLE001
            return SmsSendResult(success=False, error=str(exc))


def get_sms_provider() -> SmsProvider:
    if settings.SMS_PROVIDER == "mellipayamak":
        return MelipayamakSmsProvider(
            api_url=settings.SMS_API_URL,
            api_key=settings.SMS_API_KEY,
            sender_number=settings.SMS_SENDER_NUMBER,
            template_id=settings.SMS_OTP_TEMPLATE_ID,
        )
    return ConsoleSmsProvider()
