import pytest

from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_console_otp_is_not_exposed_in_production(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "APP_ENV", "production")
    response = await client.post("/api/v1/auth/otp/request", json={"phone": "09120001111"})
    assert response.status_code == 200
    assert response.json()["data"] == {"status": "sent"}


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
    assert tokens["user"]["is_verified"] is True
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
async def test_password_register_login_reset_flow(client):
    nid = _national_id("541111111")

    # Unregistered phone → register branch.
    response = await client.post("/api/v1/auth/check", json={"phone": "09124001122"})
    assert response.status_code == 200
    assert response.json()["data"]["registered"] is False

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": "09124001122",
            "full_name": "علی رضایی",
            "national_id": nid,
            "password": "secret-password-1",
        },
    )
    assert response.status_code == 200
    tokens = response.json()["data"]
    assert tokens["user"]["full_name"] == "علی رضایی"
    assert tokens["user"]["is_national_id_verified"] is True

    # Now the phone is registered → password branch.
    response = await client.post("/api/v1/auth/check", json={"phone": "09124001122"})
    assert response.json()["data"]["registered"] is True

    # Correct password works; wrong password gives a distinct error.
    response = await client.post(
        "/api/v1/auth/login", json={"phone": "09124001122", "password": "secret-password-1"}
    )
    assert response.status_code == 200
    response = await client.post(
        "/api/v1/auth/login", json={"phone": "09124001122", "password": "nope"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"

    # Duplicate phone / shared national id are rejected.
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": "09124001122",
            "full_name": "علی رضایی",
            "national_id": nid,
            "password": "secret-password-1",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "phone_already_registered"

    # Forgot password: OTP issue + reset, then the new password logs in.
    response = await client.post("/api/v1/auth/forgot-password", json={"phone": "09124001122"})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "issued"
    reset_code = response.json()["data"]["dev_otp"]

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"phone": "09124001122", "code": reset_code, "password": "brand-new-password"},
    )
    assert response.status_code == 200

    response = await client.post(
        "/api/v1/auth/login", json={"phone": "09124001122", "password": "brand-new-password"}
    )
    assert response.status_code == 200
    response = await client.post(
        "/api/v1/auth/login", json={"phone": "09124001122", "password": "secret-password-1"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_rejects_bad_national_id(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": "09124001133",
            "full_name": "مریم کریمی",
            "national_id": "1234567890",
            "password": "secret-password-1",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_national_id"


@pytest.mark.asyncio
async def test_register_rejects_short_password(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": "09124001144",
            "full_name": "مریم کریمی",
            "national_id": _national_id("111111111"),
            "password": "short",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "password_too_short"


@pytest.mark.asyncio
async def test_register_validation_errors_do_not_consume_rate_limit(client, fake_redis):
    from app.core.config import settings

    before = dict(fake_redis.data)
    for _ in range(settings.REGISTER_RATE_LIMIT_PER_HOUR + 1):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "phone": "09124001166",
                "full_name": "تست اعتبارسنجی",
                "national_id": "1234567890",
                "password": "secret-password-1",
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_national_id"

    # Local validation must not spend the metered Shahkar budget.
    added = {k: v for k, v in fake_redis.data.items() if k not in before}
    assert not any(k.startswith("auth:regrl:ip:") for k in added)


@pytest.mark.asyncio
async def test_password_login_locks_phone_after_failed_attempts(client):
    from app.core.config import settings

    nid = _national_id("222222222")
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "phone": "09124001155",
            "full_name": "تست مسدود",
            "national_id": nid,
            "password": "secret-password-1",
        },
    )
    assert response.status_code == 200

    for _ in range(settings.PASSWORD_MAX_ATTEMPTS):
        response = await client.post(
            "/api/v1/auth/login", json={"phone": "09124001155", "password": "wrong"}
        )
        assert response.status_code == 401

    # Even the correct password is refused while locked.
    response = await client.post(
        "/api/v1/auth/login", json={"phone": "09124001155", "password": "secret-password-1"}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "auth_blocked"
    assert response.json()["error"]["details"]["retry_after_seconds"] > 0


@pytest.mark.asyncio
async def test_login_without_password_points_to_reset(client, create_user):
    await create_user("9124009900")
    response = await client.post(
        "/api/v1/auth/login",
        json={"phone": "09124009900", "password": "whatever"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "password_not_set"


@pytest.mark.asyncio
async def test_forgot_password_is_silent_for_unknown_phone(client):
    response = await client.post("/api/v1/auth/forgot-password", json={"phone": "09124999999"})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "sent"
    assert "dev_otp" not in response.json()["data"]


@pytest.mark.asyncio
async def test_reset_password_rejects_bad_code(client, create_user):
    await create_user("9124009911")
    response = await client.post("/api/v1/auth/forgot-password", json={"phone": "09124009911"})
    assert response.json()["data"]["status"] == "issued" # dev code present but wrong below

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"phone": "09124009911", "code": "000000", "password": "..."},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "otp_invalid"


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
