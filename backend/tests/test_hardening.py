import pytest
import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.category import Category
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def test_moderation_requires_permission(client, create_user):
    customer = await create_user("09121111111", UserRole.CUSTOMER)
    admin = await create_user("09122222222", UserRole.ADMIN, permissions=["stats.read"])

    payload = {"status": "approved"}
    response = await client.patch(
        "/api/v1/businesses/00000000-0000-0000-0000-000000000000/status",
        json=payload,
        headers=auth(customer),
    )
    assert response.status_code == 403

    response = await client.patch(
        "/api/v1/businesses/00000000-0000-0000-0000-000000000000/status",
        json=payload,
        headers=auth(admin),
    )
    assert response.status_code == 403


async def test_audit_log_requires_permission(client, create_user):
    admin = await create_user("09123333333", UserRole.ADMIN, permissions=["business.approve"])
    response = await client.get("/api/v1/admin/audit-log", headers=auth(admin))
    assert response.status_code == 403

    allowed = await create_user("09124444444", UserRole.ADMIN, permissions=["admin.audit.read"])
    response = await client.get("/api/v1/admin/audit-log", headers=auth(allowed))
    assert response.status_code == 200


async def test_quote_response_does_not_leak_customer_phone(
    client, db_session, create_user
):
    await seed_categories(db_session)
    await db_session.commit()
    category = (await db_session.execute(sa.select(Category))).scalars().first()
    customer = await create_user("09125555555", UserRole.CUSTOMER)
    response = await client.post(
        "/api/v1/quotes",
        json={"title": "لوله‌کشی", "category_id": category.id, "address": "بهبهان"},
        headers=auth(customer),
    )
    assert response.status_code == 200
    assert "phone" not in response.text
