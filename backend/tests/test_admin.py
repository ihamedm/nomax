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
