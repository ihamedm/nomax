from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class SmsSendResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None


class SmsProvider:
    name = "base"

    async def send(self, phone: str, code: str) -> SmsSendResult:
        raise NotImplementedError


class ConsoleSmsProvider(SmsProvider):
    """Development provider: never touches the network.

    The OTP is mirrored in Redis by ``OtpService`` and read from the admin
    dashboard or the login dev-fill hint.
    """

    name = "console"

    async def send(self, phone: str, code: str) -> SmsSendResult:
        return SmsSendResult(success=True, provider_message_id=f"console-{phone}")


class MelipayamakSmsProvider(SmsProvider):
    """Mellipayamak shared-service (pattern) SMS sender.

    Uses a pre-approved template (``bodyId``) so messages bypass the
    free-text filtering rules. OTP sending is interactive, so the call is
    synchronous with a short timeout and a small retry budget.
    """

    name = "mellipayamak"

    def __init__(
        self,
        api_url: str,
        username: str,
        password: str,
        body_id: int,
        timeout: float = 8.0,
        max_attempts: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_url = api_url
        self.username = username
        self.password = password
        self.body_id = body_id
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)
        self._client = client

    @staticmethod
    def _to_provider_phone(phone: str) -> str:
        return phone if phone.startswith("0") else f"0{phone}"

    @staticmethod
    def _parse_response(response: httpx.Response) -> tuple[bool, str | None, str | None]:
        """Return (success, message_id, error) from a Mellipayamak reply."""
        try:
            data = response.json()
        except ValueError:
            return True, None, None

        if not isinstance(data, dict):
            return True, None, None

        ret_status = data.get("RetStatus")
        message_id = data.get("Value") or data.get("MessageId")
        if ret_status is not None and str(ret_status) not in ("1", "1.0", "True", "true"):
            return False, None, str(data.get("StrRetStatus") or ret_status)
        return True, str(message_id) if message_id is not None else None, None

    async def send(self, phone: str, code: str) -> SmsSendResult:
        payload = {
            "username": self.username,
            "password": self.password,
            "text": str(code),
            "to": self._to_provider_phone(phone),
            "bodyId": self.body_id,
        }
        last_error: str | None = None

        for attempt in range(1, self.max_attempts + 1):
            owns_client = self._client is None
            client = self._client or httpx.AsyncClient(timeout=self.timeout)
            try:
                response = await client.post(self.api_url, json=payload)
            except Exception as exc:  # noqa: BLE001 - provider failures are data, not crashes
                last_error = str(exc)
                continue
            finally:
                if owns_client:
                    await client.aclose()

            if not 200 <= response.status_code < 300:
                last_error = f"provider_http_{response.status_code}"
                # 4xx means bad credentials/template: retrying cannot help.
                if 400 <= response.status_code < 500:
                    break
                continue

            success, message_id, error = self._parse_response(response)
            if success:
                return SmsSendResult(success=True, provider_message_id=message_id)
            last_error = error or "provider_rejected"
            if attempt < self.max_attempts:
                continue

        return SmsSendResult(success=False, error=last_error or "provider_unavailable")


def get_sms_provider() -> SmsProvider:
    if settings.SMS_PROVIDER == "mellipayamak":
        return MelipayamakSmsProvider(
            api_url=settings.SMS_API_URL,
            username=settings.SMS_USERNAME,
            password=settings.SMS_PASSWORD,
            body_id=settings.SMS_OTP_BODY_ID,
            timeout=settings.SMS_TIMEOUT_SECONDS,
            max_attempts=settings.SMS_MAX_ATTEMPTS,
        )
    return ConsoleSmsProvider()
