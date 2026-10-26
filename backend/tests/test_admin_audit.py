import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.admin import AuditLog
from app.models.user import UserRole


@pytest.mark.asyncio
async def test_role_and_permission_updates_are_audited(client, create_user, db_session):
    admin = await create_user("9110000010", role=UserRole.SUPERADMIN)
    target = await create_user("9120000010")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id, admin.role.value)}"}

    response = await client.patch(
        f"/api/v1/admin/users/{target.id}/role",
        json={"role": "admin"},
        headers=headers,
    )
    assert response.status_code == 200

    response = await client.patch(
        f"/api/v1/admin/users/{target.id}/permissions",
        json={"permissions": ["business.read", "business.approve"]},
        headers=headers,
    )
    assert response.status_code == 200

    logs = (
        await db_session.execute(select(AuditLog).order_by(AuditLog.created_at))
    ).scalars().all()
    actions = [log.action for log in logs]
    assert "admin.user.role.updated" in actions
    assert "admin.user.permissions.updated" in actions

    role_log = next(log for log in logs if log.action == "admin.user.role.updated")
    assert role_log.entity_id == str(target.id)
    assert role_log.before["role"] == "customer"
    assert role_log.after["role"] == "admin"


@pytest.mark.asyncio
async def test_non_superadmin_admin_cannot_change_roles(client, create_user):
    admin = await create_user("9110000011", role=UserRole.ADMIN, permissions=["user.manage"])
    target = await create_user("9120000011")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id, admin.role.value)}"}

    response = await client.patch(
        f"/api/v1/admin/users/{target.id}/role",
        json={"role": "superadmin"},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_permission_catalog_for_superadmin(client, create_user):
    admin = await create_user("9110000013", role=UserRole.SUPERADMIN)
    customer = await create_user("9120000013")
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin.id, admin.role.value)}"}
    customer_headers = {"Authorization": f"Bearer {create_access_token(customer.id, customer.role.value)}"}

    response = await client.get("/api/v1/admin/permissions", headers=admin_headers)
    assert response.status_code == 200
    codes = {item["code"] for item in response.json()["data"]["items"]}
    assert {"business.read", "user.manage", "admin.dev"} <= codes

    response = await client.get("/api/v1/admin/permissions", headers=customer_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unknown_permission_code_is_rejected(client, create_user):
    admin = await create_user("9110000012", role=UserRole.SUPERADMIN)
    target = await create_user("9120000012")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id, admin.role.value)}"}

    response = await client.patch(
        f"/api/v1/admin/users/{target.id}/permissions",
        json={"permissions": ["business.read", "made.up.permission"]},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["permissions"] == ["made.up.permission"]
