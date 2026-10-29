import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _category(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    return (await db_session.execute(sa.select(Category))).scalars().first()


async def test_bookmark_roundtrip_and_detail_flag(client, db_session, create_user):
    user = await create_user("09130000001")
    category = await _category(db_session)
    business = Business(
        owner_id=user.id,
        category_id=category.id,
        name="فروشگاه نمونه",
        slug="bookmark-shop",
        address="بهبهان",
        status=BusinessStatus.APPROVED,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)

    saved = await client.post(
        f"/api/v1/me/bookmarks/{business.id}", headers=auth(user)
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["saved"] is True

    listing = await client.get("/api/v1/me/bookmarks", headers=auth(user))
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["data"]["items"]] == [str(business.id)]

    detail = await client.get(
        f"/api/v1/businesses/{business.slug}", headers=auth(user)
    )
    assert detail.json()["data"]["is_saved"] is True

    public_detail = await client.get(f"/api/v1/businesses/{business.slug}")
    assert public_detail.json()["data"]["is_saved"] is False

    removed = await client.delete(
        f"/api/v1/me/bookmarks/{business.id}", headers=auth(user)
    )
    assert removed.status_code == 200
    assert removed.json()["data"]["saved"] is False
    assert (await client.get("/api/v1/me/bookmarks", headers=auth(user))).json()["data"]["items"] == []


async def test_bookmarks_require_auth_and_approved_business(client, db_session, create_user):
    assert (await client.get("/api/v1/me/bookmarks")).status_code == 401

    user = await create_user("09130000002", UserRole.OWNER)
    category = await _category(db_session)
    pending = Business(
        owner_id=user.id,
        category_id=category.id,
        name="در انتظار",
        slug="bookmark-pending",
        address="بهبهان",
        status=BusinessStatus.PENDING,
    )
    db_session.add(pending)
    await db_session.commit()
    await db_session.refresh(pending)

    response = await client.post(
        f"/api/v1/me/bookmarks/{pending.id}", headers=auth(user)
    )
    assert response.status_code == 404
