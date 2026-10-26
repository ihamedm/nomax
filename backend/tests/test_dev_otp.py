import pytest

from app.core.security import create_access_token
from app.models.user import UserRole


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_customer_cannot_read_dev_otps(client, create_user):
    customer = await create_user("9120000001")
    token = create_access_token(customer.id, customer.role.value)

    response = await client.get("/api/v1/admin/dev/otps", headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"

    response = await client.get("/api/v1/admin/dev/otps/09120000002", headers=_auth(token))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_can_read_live_dev_otp(client, create_user):
    admin = await create_user("9110000001", role=UserRole.SUPERADMIN)
    token = create_access_token(admin.id, admin.role.value)

    issued = await client.post("/api/v1/auth/otp/request", json={"phone": "09120000002"})
    assert issued.status_code == 200
    dev_otp = issued.json()["data"]["dev_otp"]

    response = await client.get("/api/v1/admin/dev/otps", headers=_auth(token))
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    matches = [item for item in items if item["phone"] == "9120000002"]
    assert len(matches) == 1
    assert matches[0]["otp"] == dev_otp
    assert matches[0]["ttl_seconds"] > 0
    assert matches[0]["expires_at"]

    single = await client.get("/api/v1/admin/dev/otps/09120000002", headers=_auth(token))
    assert single.status_code == 200
    assert single.json()["data"]["otp"] == dev_otp


@pytest.mark.asyncio
async def test_dev_otp_lookup_returns_404_when_missing(client, create_user):
    admin = await create_user("9110000002", role=UserRole.SUPERADMIN)
    token = create_access_token(admin.id, admin.role.value)

    response = await client.get("/api/v1/admin/dev/otps/09129999999", headers=_auth(token))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_dev_otp_endpoints_hidden_in_production(monkeypatch):
    from app.core.config import settings
    from app.main import create_app

    monkeypatch.setattr(settings, "APP_ENV", "production")
    paths = {route.path for route in create_app().routes}
    assert "/api/v1/admin/dev/otps" not in paths

    monkeypatch.setattr(settings, "DEV_OTP_ENABLED", False)
    monkeypatch.setattr(settings, "APP_ENV", "local")
    paths = {route.path for route in create_app().routes}
    assert "/api/v1/admin/dev/otps" not in paths
