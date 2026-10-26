import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _setup(db_session, create_user):
    await seed_categories(db_session)
    await db_session.commit()
    category = (await db_session.execute(sa.select(Category))).scalars().first()
    owner = await create_user("09140000001", UserRole.OWNER)
    business = Business(owner_id=owner.id, category_id=category.id, name="biz",
                        slug="biz-admin", address="بهبهان", status=BusinessStatus.PENDING)
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return owner, business


async def test_admin_approves_business(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    admin = await create_user("09140000002", UserRole.ADMIN, permissions=["business.approve"])
    response = await client.patch(f"/api/v1/admin/businesses/{business.id}/approve", headers=auth(admin))
    assert response.status_code == 200
    await db_session.refresh(business)
    assert business.status == BusinessStatus.APPROVED


async def test_is_verified_requires_admin_verified_license(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)

    missing = await client.patch(
        f"/api/v1/admin/businesses/{business.id}/verify-license",
        headers=auth(await create_user("09140000003", UserRole.ADMIN, permissions=["business.license.verify"])),
    )
    assert missing.status_code == 404

    license_res = await client.post(
        f"/api/v1/businesses/{business.id}/license",
        json={"license_number": "123"},
        headers=auth(owner),
    )
    assert license_res.status_code == 200

    admin = await create_user("09140000004", UserRole.ADMIN, permissions=["business.license.verify"])
    verified = await client.patch(f"/api/v1/admin/businesses/{business.id}/verify-license", headers=auth(admin))
    assert verified.status_code == 200
    await db_session.refresh(business)
    assert business.is_verified is True


async def test_max_three_custom_tags(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    ok = await client.post(f"/api/v1/businesses/{business.id}/tags",
                           json={"tags": ["a", "b", "c"]}, headers=auth(owner))
    assert ok.status_code == 200
    too_many = await client.post(f"/api/v1/businesses/{business.id}/tags",
                                 json={"tags": ["a", "b", "c", "d"]}, headers=auth(owner))
    assert too_many.status_code == 422
