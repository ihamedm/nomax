import json

import httpx
import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.services import shahkar_service


def _client_returning(payload: dict, status: int = 200, seen: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=payload)

    transport = httpx.MockTransport(handler)
    client_cls = httpx.AsyncClient
    return lambda *args, **kwargs: client_cls(transport=transport, **kwargs)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "SHAHKAR_API_KEY", "test-token")


async def test_match_sends_bearer_token_and_normalized_mobile(monkeypatch):
    seen: list[httpx.Request] = []
    monkeypatch.setattr(
        shahkar_service.httpx,
        "AsyncClient",
        _client_returning({"success": True, "code": 200, "data": True}, seen=seen),
    )

    await shahkar_service.verify_mobile_owner("0010007700", "9120000000")

    assert seen[0].headers["Authorization"] == "Bearer test-token"
    assert json.loads(seen[0].content) == {
        "nationalCode": "0010007700",
        "mobile": "09120000000",
        "isCompany": False,
    }


async def test_data_false_is_mismatch(monkeypatch):
    monkeypatch.setattr(
        shahkar_service.httpx,
        "AsyncClient",
        _client_returning(
            {
                "success": True,
                "code": 0,
                "data": False,
                "message": "عدم انطباق اطلاعات وارد شده",
            }
        ),
    )

    with pytest.raises(AppError) as exc:
        await shahkar_service.verify_mobile_owner("0010007700", "09120000000")

    assert exc.value.code == "shahkar_mismatch"
    assert exc.value.details["provider_message"] == "عدم انطباق اطلاعات وارد شده"


async def test_rejected_input_is_invalid_input(monkeypatch):
    monkeypatch.setattr(
        shahkar_service.httpx,
        "AsyncClient",
        _client_returning(
            {"success": False, "code": 422, "message": "کد ملی نامعتبر است"}
        ),
    )

    with pytest.raises(AppError) as exc:
        await shahkar_service.verify_mobile_owner("0010007700", "09120000000")

    assert exc.value.code == "shahkar_invalid_input"
    assert exc.value.details["provider_message"] == "کد ملی نامعتبر است"
    assert exc.value.details["provider_code"] == 422


async def test_bad_token_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        shahkar_service.httpx,
        "AsyncClient",
        _client_returning({"success": False, "code": 401, "message": "unauthorized"}),
    )

    with pytest.raises(AppError) as exc:
        await shahkar_service.verify_mobile_owner("0010007700", "09120000000")

    assert exc.value.code == "shahkar_unavailable"
