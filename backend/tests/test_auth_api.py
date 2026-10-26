import pytest

from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}


@pytest.mark.asyncio
async def test_otp_flow_end_to_end(client, db_session, fake_redis):
    response = await client.post("/api/v1/auth/otp/request", json={"phone": "09123456789"})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "issued"
    dev_otp = body["data"]["dev_otp"]
    assert len(dev_otp) == 6

    response = await client.post("/api/v1/auth/otp/verify", json={"phone": "09123456789", "code": dev_otp})
    assert response.status_code == 200
    tokens = response.json()["data"]
    assert tokens["access"]
    assert tokens["refresh"]
    assert tokens["user"]["is_phone_verified"] is True
    assert tokens["user"]["role"] == "customer"

    response = await client.post("/api/v1/auth/otp/verify", json={"phone": "09123456789", "code": dev_otp})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "otp_invalid"


@pytest.mark.asyncio
async def test_refresh_rotation_and_logout(client, fake_redis):
    request = await client.post("/api/v1/auth/otp/request", json={"phone": "09123456789"})
    dev_otp = request.json()["data"]["dev_otp"]

    verify = await client.post("/api/v1/auth/otp/verify", json={"phone": "09123456789", "code": dev_otp})
    refresh_token = verify.json()["data"]["refresh"]

    refresh = await client.post("/api/v1/auth/refresh", json={"refresh": refresh_token})
    assert refresh.status_code == 200
    new_refresh = refresh.json()["data"]["refresh"]
    assert new_refresh != refresh_token

    reuse = await client.post("/api/v1/auth/refresh", json={"refresh": refresh_token})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "token_revoked"

    logout = await client.post("/api/v1/auth/logout", json={"refresh": new_refresh})
    assert logout.status_code == 200


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_unauthorized"


@pytest.mark.asyncio
async def test_otp_verification_is_attempt_limited(client):
    issued = await client.post("/api/v1/auth/otp/request", json={"phone": "09123334444"})
    code = issued.json()["data"]["dev_otp"]

    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/otp/verify", json={"phone": "09123334444", "code": "000000"}
        )
        assert response.status_code == 401

    response = await client.post(
        "/api/v1/auth/otp/verify", json={"phone": "09123334444", "code": code}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "otp_invalid"


@pytest.mark.asyncio
async def test_deleted_account_cannot_log_in(client, create_user):
    await create_user("9155555555", deleted=True)

    issued = await client.post("/api/v1/auth/otp/request", json={"phone": "09155555555"})
    code = issued.json()["data"]["dev_otp"]
    response = await client.post(
        "/api/v1/auth/otp/verify", json={"phone": "09155555555", "code": code}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_disabled"


def _national_id(base9: str) -> str:
    weights = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(base9, weights))
    remainder = total % 11
    return base9 + str(remainder if remainder < 2 else 11 - remainder)


@pytest.mark.asyncio
async def test_national_id_cannot_be_shared_or_overwritten(client):
    first_nid = _national_id("123456789")
    second_nid = _national_id("987654321")
    assert first_nid != second_nid

    issued = await client.post("/api/v1/auth/otp/request", json={"phone": "09121112222"})
    code = issued.json()["data"]["dev_otp"]
    response = await client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": "09121112222", "code": code, "national_id": first_nid},
    )
    assert response.status_code == 200
    assert response.json()["data"]["user"]["national_id"] == first_nid

    issued = await client.post("/api/v1/auth/otp/request", json={"phone": "09123332222"})
    code = issued.json()["data"]["dev_otp"]
    response = await client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": "09123332222", "code": code, "national_id": first_nid},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"

    issued = await client.post("/api/v1/auth/otp/request", json={"phone": "09121112222"})
    code = issued.json()["data"]["dev_otp"]
    response = await client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": "09121112222", "code": code, "national_id": second_nid},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_admin_endpoints_permissions(client, create_user):
    user = await create_user("9123456789")
    token = create_access_token(user.id, user.role.value)
    client.headers.update({"Authorization": f"Bearer {token}"})

    response = await client.get("/api/v1/admin/me")
    assert response.status_code == 200
    assert response.json()["data"]["is_superadmin"] is False

    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
