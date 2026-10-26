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
    owner = await create_user("09130000001", UserRole.OWNER)
    customer = await create_user("09130000002")
    business = Business(owner_id=owner.id, category_id=category.id, name="b", slug="b-rev",
                        address="بهبهان", status=BusinessStatus.APPROVED)
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return owner, customer, business


async def test_owner_can_reply_to_review(client, db_session, create_user):
    owner, customer, business = await _setup(db_session, create_user)
    created = await client.post(f"/api/v1/businesses/{business.slug}/reviews",
                                json={"rating": 5, "text": "عالی"}, headers=auth(customer))
    assert created.status_code == 200
    review_id = created.json()["data"]["id"]

    reply = await client.post(f"/api/v1/reviews/{review_id}/reply",
                              json={"reply": "ممنون"}, headers=auth(owner))
    assert reply.status_code == 200
    assert reply.json()["data"]["reply"] == "ممنون"


async def test_rating_updates_on_approval(client, db_session, create_user):
    owner, customer, business = await _setup(db_session, create_user)
    created = await client.post(f"/api/v1/businesses/{business.slug}/reviews",
                                json={"rating": 4}, headers=auth(customer))
    review_id = created.json()["data"]["id"]

    admin = await create_user("09130000003", UserRole.ADMIN, permissions=["review.moderate"])
    approved = await client.patch(f"/api/v1/businesses/reviews/{review_id}/status",
                                  json={"status": "approved"}, headers=auth(admin))
    assert approved.status_code == 200
    await db_session.refresh(business)
    assert business.rating_count == 1
    assert business.rating_avg == 4
