import pytest

from app.core.security import create_access_token
from app.models.user import UserRole


@pytest.mark.asyncio
async def test_admin_me_requires_auth(client):
    response = await client.get("/api/v1/admin/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_unauthorized"


@pytest.mark.asyncio
async def test_superadmin_can_list_users(client, create_user):
    admin = await create_user("9111222333", role=UserRole.SUPERADMIN)
    await create_user("9123456789", role=UserRole.CUSTOMER)

    token = create_access_token(admin.id, admin.role.value)
    client.headers.update({"Authorization": f"Bearer {token}"})

    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 200
    phones = {item["phone"] for item in response.json()["data"]["items"]}
    assert {"9111222333", "9123456789"} <= phones


@pytest.mark.asyncio
async def test_users_list_is_paginated(client, create_user):
    admin = await create_user("9111222300", role=UserRole.SUPERADMIN)
    for index in range(5):
        await create_user(f"91234567{index:02d}", role=UserRole.CUSTOMER)

    headers = {"Authorization": f"Bearer {create_access_token(admin.id, admin.role.value)}"}

    first = await client.get("/api/v1/admin/users?page=1&per_page=2", headers=headers)
    assert first.status_code == 200
    payload = first.json()
    assert payload["meta"] == {"page": 1, "per_page": 2, "total": 6, "pages": 3}
    assert len(payload["data"]["items"]) == 2

    last = await client.get("/api/v1/admin/users?page=3&per_page=2", headers=headers)
    assert last.status_code == 200
    assert len(last.json()["data"]["items"]) == 2
    first_ids = {item["id"] for item in payload["data"]["items"]}
    last_ids = {item["id"] for item in last.json()["data"]["items"]}
    assert first_ids.isdisjoint(last_ids)

    beyond = await client.get("/api/v1/admin/users?page=9&per_page=2", headers=headers)
    assert beyond.status_code == 200
    assert beyond.json()["data"]["items"] == []

    invalid = await client.get("/api/v1/admin/users?per_page=500", headers=headers)
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_users_list_search_by_name_and_phone(client, create_user):
    admin = await create_user("9111222400", role=UserRole.SUPERADMIN)
    await create_user("9121111001", full_name="زهرا احمدی")
    await create_user("9121111002", full_name="محمد رضایی")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id, admin.role.value)}"}

    by_name = await client.get("/api/v1/admin/users?q=احمدی", headers=headers)
    assert by_name.status_code == 200
    assert [item["phone"] for item in by_name.json()["data"]["items"]] == ["9121111001"]

    # Operators usually type the number with a leading zero; stored phones omit it.
    by_phone = await client.get("/api/v1/admin/users?q=09121111002", headers=headers)
    assert by_phone.status_code == 200
    assert [item["phone"] for item in by_phone.json()["data"]["items"]] == ["9121111002"]

    by_prefix = await client.get("/api/v1/admin/users?q=9121111001", headers=headers)
    assert by_prefix.status_code == 200
    assert [item["phone"] for item in by_prefix.json()["data"]["items"]] == ["9121111001"]

    no_match = await client.get("/api/v1/admin/users?q=9999999", headers=headers)
    assert no_match.status_code == 200
    assert no_match.json()["data"]["items"] == []
