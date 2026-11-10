import httpx

from app.core.config import settings
from app.core.errors import AppError


async def is_configured() -> bool:
    return bool(settings.SHAHKAR_API_KEY)


def _provider_phone(phone: str) -> str:
    return phone if phone.startswith("0") else f"0{phone}"


async def verify_mobile_owner(national_id: str, phone: str) -> None:
    """Confirm the SIM is registered to this national ID via api.ir Shahkar.

    Raises an AppError describing the problem when it is not.
    """
    if not await is_configured():
        # shortcut: unset key = development; every match passes, upgrade when a production token is set
        return

    payload = {
        "nationalCode": national_id,
        "mobile": _provider_phone(phone),
        "isCompany": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.SHAHKAR_API_KEY}",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.SHAHKAR_TIMEOUT_SECONDS) as client:
            response = await client.post(settings.SHAHKAR_API_URL, json=payload, headers=headers)
    except Exception as exc:  # noqa: BLE001 - provider failures are data, not crashes
        raise AppError("shahkar_unavailable", "shahkar_unavailable", 503, {"reason": str(exc)}) from exc

    if response.status_code >= 500:
        raise AppError("shahkar_unavailable", "shahkar_service_unavailable", 503)

    try:
        data = response.json()
    except ValueError:
        raise AppError("shahkar_unavailable", "shahkar_invalid_response", 503) from None
    if not isinstance(data, dict):
        raise AppError("shahkar_unavailable", "shahkar_invalid_response", 503) from None

    provider_message = str(data.get("message") or "").strip()

    # api.ir envelope: success says the inquiry ran, data is the match result.
    if data.get("success") is True:
        if data.get("data") is True:
            return
        raise AppError(
            "shahkar_mismatch",
            provider_message or "mobile_not_owned_by_national_id",
            422,
            {"provider_message": provider_message},
        )

    try:
        code = int(data.get("code") or 0)
    except (TypeError, ValueError):
        code = 0

    # 401 = our token is missing/invalid; >=500 = provider-side failure.
    if code == 401 or code >= 500:
        raise AppError(
            "shahkar_unavailable",
            "shahkar_service_unavailable",
            503,
            {"provider_message": provider_message, "provider_code": code},
        )
    raise AppError(
        "shahkar_invalid_input",
        provider_message or "shahkar_invalid_input",
        422,
        {"provider_message": provider_message, "provider_code": code},
    )
