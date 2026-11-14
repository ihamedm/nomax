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
    owner = await create_user("09131000001", UserRole.OWNER)
    customer = await create_user("09131000002")
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="liked",
        slug="liked-biz",
        address="بهبهان",
        status=BusinessStatus.APPROVED,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return owner, customer, business


async def test_like_and_unlike_are_idempotent(client, db_session, create_user):
    _, customer, business = await _setup(db_session, create_user)

    liked = await client.post(f"/api/v1/me/likes/{business.id}", headers=auth(customer))
    assert liked.status_code == 200
    assert liked.json()["data"] == {"liked": True, "like_count": 1}

    again = await client.post(f"/api/v1/me/likes/{business.id}", headers=auth(customer))
    assert again.json()["data"] == {"liked": True, "like_count": 1}

    detail = await client.get(f"/api/v1/businesses/{business.slug}", headers=auth(customer))
    assert detail.json()["data"]["like_count"] == 1
    assert detail.json()["data"]["is_liked"] is True

    anonymous = await client.get(f"/api/v1/businesses/{business.slug}")
    assert anonymous.json()["data"]["like_count"] == 1
    assert anonymous.json()["data"]["is_liked"] is False

    unliked = await client.delete(f"/api/v1/me/likes/{business.id}", headers=auth(customer))
    assert unliked.json()["data"] == {"liked": False, "like_count": 0}

    again = await client.delete(f"/api/v1/me/likes/{business.id}", headers=auth(customer))
    assert again.json()["data"] == {"liked": False, "like_count": 0}

    detail = await client.get(f"/api/v1/businesses/{business.slug}")
    assert detail.json()["data"]["like_count"] == 0


async def test_like_requires_login(client, db_session, create_user):
    _, _, business = await _setup(db_session, create_user)
    response = await client.post(f"/api/v1/me/likes/{business.id}")
    assert response.status_code == 401
