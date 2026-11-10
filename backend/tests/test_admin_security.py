import pytest

from app.core.security import create_access_token, create_refresh_token
from app.models.user import UserRole


def _headers(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


@pytest.mark.asyncio
async def test_non_superadmin_cannot_use_security_endpoints(client, create_user):
    customer = await create_user("9124000200", role=UserRole.CUSTOMER)
    response = await client.get("/api/v1/admin/security", headers=_headers(customer))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rate_limits_are_listed_and_reset(client, create_user, fake_redis):
    admin = await create_user("9111222400", role=UserRole.SUPERADMIN)
    fake_redis.data["auth:regrl:ip:1.2.3.4"] = 5
    fake_redis.ttls["auth:regrl:ip:1.2.3.4"] = 900

    response = await client.get("/api/v1/admin/security", headers=_headers(admin))
    assert response.status_code == 200
    entries = response.json()["data"]["rate_limits"]
    entry = next(item for item in entries if item["key"] == "auth:regrl:ip:1.2.3.4")
    assert entry["kind"] == "register_ip"
    assert entry["subject"] == "1.2.3.4"
    assert entry["count"] == 5
    assert entry["ttl_seconds"] == 900

    response = await client.post(
        "/api/v1/admin/security/rate-limits/reset",
        json={"key": "auth:regrl:ip:1.2.3.4"},
        headers=_headers(admin),
    )
    assert response.status_code == 200
    assert "auth:regrl:ip:1.2.3.4" not in fake_redis.data

    # Arbitrary Redis keys must not be deletable through this endpoint.
    response = await client.post(
        "/api/v1/admin/security/rate-limits/reset",
        json={"key": "some:secret:key"},
        headers=_headers(admin),
    )
    assert response.status_code == 422

    fake_redis.data["otp:rl:ip:5.6.7.8"] = 3
    response = await client.post(
        "/api/v1/admin/security/rate-limits/reset-all",
        json={},
        headers=_headers(admin),
    )
    assert response.status_code == 200
    assert "otp:rl:ip:5.6.7.8" not in fake_redis.data


@pytest.mark.asyncio
async def test_blocked_phone_cannot_login_or_use_tokens(client, create_user, fake_redis):
    admin = await create_user("9111222401", role=UserRole.SUPERADMIN)
    target = await create_user("9124000201")

    blocked = await client.post(
        "/api/v1/admin/security/blocks",
        json={"kind": "phone", "value": "09124000201"},
        headers=_headers(admin),
    )
    assert blocked.status_code == 200
    assert fake_redis.data.get("auth:block:phone:9124000201") == "1"

    # Existing access tokens stop working immediately.
    response = await client.get("/api/v1/me/bookmarks", headers=_headers(target))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_blocked"

    # New password logins are refused too.
    response = await client.post(
        "/api/v1/auth/login",
        json={"phone": "09124000201", "password": "whatever"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_blocked"

    listed = await client.get("/api/v1/admin/security", headers=_headers(admin))
    assert any(
        item["kind"] == "phone" and item["subject"] == "9124000201"
        for item in listed.json()["data"]["blocks"]
    )

    removed = await client.delete(
        "/api/v1/admin/security/blocks/phone/09124000201", headers=_headers(admin)
    )
    assert removed.status_code == 200
    response = await client.get("/api/v1/me/bookmarks", headers=_headers(target))
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ip_blocks_validate_and_can_be_removed(client, create_user, fake_redis):
    admin = await create_user("9111222404", role=UserRole.SUPERADMIN)

    invalid = await client.post(
        "/api/v1/admin/security/blocks",
        json={"kind": "ip", "value": "not-an-ip"},
        headers=_headers(admin),
    )
    assert invalid.status_code == 422

    created = await client.post(
        "/api/v1/admin/security/blocks",
        json={"kind": "ip", "value": "203.0.113.9"},
        headers=_headers(admin),
    )
    assert created.status_code == 200
    assert fake_redis.data["auth:block:ip:203.0.113.9"] == "1"

    removed = await client.delete(
        "/api/v1/admin/security/blocks/ip/203.0.113.9", headers=_headers(admin)
    )
    assert removed.status_code == 200
    assert "auth:block:ip:203.0.113.9" not in fake_redis.data


@pytest.mark.asyncio
async def test_force_logout_revokes_access_and_refresh_tokens(client, create_user):
    admin = await create_user("9111222402", role=UserRole.SUPERADMIN)
    target = await create_user("9124000202")

    access = create_access_token(target.id, target.role.value)
    refresh, _jti, _fam = create_refresh_token(target.id, target.role.value)
    headers = {"Authorization": f"Bearer {access}"}
    assert (await client.get("/api/v1/me/bookmarks", headers=headers)).status_code == 200

    response = await client.post(
        "/api/v1/admin/security/users/logout",
        json={"phone": "09124000202"},
        headers=_headers(admin),
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(target.id)

    response = await client.get("/api/v1/me/bookmarks", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_revoked"

    response = await client.post("/api/v1/auth/refresh", json={"refresh": refresh})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_revoked"


@pytest.mark.asyncio
async def test_force_logout_unknown_or_self(client, create_user):
    admin = await create_user("9111222403", role=UserRole.SUPERADMIN)

    response = await client.post(
        "/api/v1/admin/security/users/logout",
        json={"phone": "09129999999"},
        headers=_headers(admin),
    )
    assert response.status_code == 404

    response = await client.post(
        "/api/v1/admin/security/users/logout",
        json={"phone": "09111222403"},
        headers=_headers(admin),
    )
    assert response.status_code == 422
