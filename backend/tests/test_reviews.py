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


async def test_rejected_review_is_hidden_and_not_rated(client, db_session, create_user):
    owner, customer, business = await _setup(db_session, create_user)
    created = await client.post(f"/api/v1/businesses/{business.slug}/reviews",
                                json={"rating": 5, "text": "نامناسب"}, headers=auth(customer))
    review_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "pending"

    admin = await create_user("09130000004", UserRole.ADMIN, permissions=["review.moderate"])
    rejected = await client.patch(f"/api/v1/businesses/reviews/{review_id}/status",
                                  json={"status": "rejected"}, headers=auth(admin))
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "rejected"

    detail = await client.get(f"/api/v1/businesses/{business.slug}")
    assert detail.json()["data"]["reviews"] == []
    await db_session.refresh(business)
    assert business.rating_count == 0


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


async def test_private_review_is_owner_only_and_not_moderated(client, db_session, create_user):
    owner, customer, business = await _setup(db_session, create_user)
    created = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 2, "text": "فقط برای مالک", "is_private": True},
        headers=auth(customer),
    )
    assert created.status_code == 200
    review_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "private"
    assert created.json()["data"]["is_private"] is True

    public = await client.get(f"/api/v1/businesses/{business.slug}")
    assert public.json()["data"]["reviews"] == []
    await db_session.refresh(business)
    assert business.rating_count == 0

    admin = await create_user(
        "09130000005", UserRole.ADMIN, permissions=["review.read", "review.moderate"]
    )
    admin_list = await client.get("/api/v1/admin/reviews?status=pending", headers=auth(admin))
    assert admin_list.status_code == 200
    assert admin_list.json()["data"]["items"] == []

    moderate = await client.patch(
        f"/api/v1/businesses/reviews/{review_id}/status",
        json={"status": "approved"},
        headers=auth(admin),
    )
    assert moderate.status_code == 422
    assert moderate.json()["error"]["code"] == "private_review_not_moderatable"

    owner_inbox = await client.get("/api/v1/me/reviews", headers=auth(owner))
    assert owner_inbox.status_code == 200
    payload = owner_inbox.json()["data"]
    assert payload["unread_count"] == 1
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["id"] == review_id
    assert item["is_private"] is True
    assert item["business_name"] == business.name
    assert item["author_name"] == "کاربر نومکس"

    other_user_inbox = await client.get("/api/v1/me/reviews", headers=auth(customer))
    assert other_user_inbox.json()["data"]["items"] == []

    count = await client.get("/api/v1/me/reviews/unread-count", headers=auth(owner))
    assert count.json()["data"]["count"] == 1
    seen = await client.patch("/api/v1/me/reviews/mark-seen", headers=auth(owner))
    assert seen.json()["data"]["unread_count"] == 0
    count = await client.get("/api/v1/me/reviews/unread-count", headers=auth(owner))
    assert count.json()["data"]["count"] == 0
    again = await client.get("/api/v1/me/reviews", headers=auth(owner))
    assert again.json()["data"]["items"][0]["id"] == review_id


async def test_pending_review_notifies_owner_and_public_after_approval(
    client, db_session, create_user
):
    owner, customer, business = await _setup(db_session, create_user)
    created = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 5, "text": "عالی بود"},
        headers=auth(customer),
    )
    review_id = created.json()["data"]["id"]

    count = await client.get("/api/v1/me/reviews/unread-count", headers=auth(owner))
    assert count.json()["data"]["count"] == 1

    detail = await client.get(
        f"/api/v1/businesses/{business.slug}", headers=auth(customer)
    )
    assert detail.json()["data"]["reviews"] == []
    assert detail.json()["data"]["my_review"] == {
        "id": review_id,
        "status": "pending",
        "is_private": False,
    }

    admin = await create_user(
        "09130000006", UserRole.ADMIN, permissions=["review.read", "review.moderate"]
    )
    approved = await client.patch(
        f"/api/v1/businesses/reviews/{review_id}/status",
        json={"status": "approved"},
        headers=auth(admin),
    )
    assert approved.status_code == 200

    public = await client.get(f"/api/v1/businesses/{business.slug}")
    reviews = public.json()["data"]["reviews"]
    assert len(reviews) == 1
    assert reviews[0]["id"] == review_id
    assert reviews[0]["author_name"] == "کاربر نومکس"
    await db_session.refresh(business)
    assert business.rating_count == 1
    assert business.rating_avg == 5

    rejected = await client.patch(
        f"/api/v1/businesses/reviews/{review_id}/status",
        json={"status": "rejected"},
        headers=auth(admin),
    )
    assert rejected.status_code == 200
    await db_session.refresh(business)
    assert business.rating_count == 0
    assert business.rating_avg == 0


async def test_review_cannot_be_duplicated_or_self_reviewed(client, db_session, create_user):
    owner, customer, business = await _setup(db_session, create_user)

    own = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 5},
        headers=auth(owner),
    )
    assert own.status_code == 403
    assert own.json()["error"]["code"] == "cannot_review_own_business"

    first = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 4},
        headers=auth(customer),
    )
    assert first.status_code == 200
    duplicate = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 5},
        headers=auth(customer),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "review_already_exists"


async def test_owner_can_approve_or_reject_public_reviews(client, db_session, create_user):
    owner, customer, business = await _setup(db_session, create_user)
    created = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 4, "text": "نظر برای مالک"},
        headers=auth(customer),
    )
    review_id = created.json()["data"]["id"]

    approved = await client.patch(
        f"/api/v1/businesses/reviews/{review_id}/status",
        json={"status": "approved"},
        headers=auth(owner),
    )
    assert approved.status_code == 200
    await db_session.refresh(business)
    assert business.rating_count == 1
    assert business.rating_avg == 4

    rejected = await client.patch(
        f"/api/v1/businesses/reviews/{review_id}/status",
        json={"status": "rejected"},
        headers=auth(owner),
    )
    assert rejected.status_code == 200
    await db_session.refresh(business)
    assert business.rating_count == 0


async def test_other_owner_cannot_moderate_reviews(client, db_session, create_user):
    owner, customer, business = await _setup(db_session, create_user)
    created = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 5},
        headers=auth(customer),
    )
    review_id = created.json()["data"]["id"]
    other_owner = await create_user("09130000007", UserRole.OWNER)

    response = await client.patch(
        f"/api/v1/businesses/reviews/{review_id}/status",
        json={"status": "approved"},
        headers=auth(other_owner),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert response.json()["error"]["message"] == "review_moderation_forbidden"


async def test_review_text_is_limited_to_300_chars(client, db_session, create_user):
    owner, customer, business = await _setup(db_session, create_user)
    long_text = "ن" * 301
    response = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 5, "text": long_text},
        headers=auth(customer),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "review_too_long"

    ok = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 5, "text": "ن" * 300},
        headers=auth(customer),
    )
    assert ok.status_code == 200


async def test_admin_review_list_filters_and_paginates(client, db_session, create_user):
    owner, customer, business = await _setup(db_session, create_user)
    second = await create_user("09130000008")
    first = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 5, "text": "اول"},
        headers=auth(customer),
    )
    second_review = await client.post(
        f"/api/v1/businesses/{business.slug}/reviews",
        json={"rating": 2, "text": "دوم"},
        headers=auth(second),
    )
    admin = await create_user(
        "09130000009", UserRole.ADMIN, permissions=["review.read", "review.moderate"]
    )
    await client.patch(
        f"/api/v1/businesses/reviews/{first.json()['data']['id']}/status",
        json={"status": "approved"},
        headers=auth(admin),
    )

    page = await client.get(
        f"/api/v1/admin/reviews?business_id={business.id}&page=1&per_page=1",
        headers=auth(admin),
    )
    assert page.status_code == 200
    body = page.json()
    assert body["meta"]["total"] == 2
    assert body["meta"]["pages"] == 2
    assert len(body["data"]["items"]) == 1

    approved = await client.get(
        "/api/v1/admin/reviews?status=approved", headers=auth(admin)
    )
    assert approved.status_code == 200
    assert [item["id"] for item in approved.json()["data"]["items"]] == [
        first.json()["data"]["id"]
    ]

    unapproved = await client.get(
        "/api/v1/admin/reviews?status=unapproved", headers=auth(admin)
    )
    assert [item["id"] for item in unapproved.json()["data"]["items"]] == [
        second_review.json()["data"]["id"]
    ]

    search = await client.get(
        "/api/v1/admin/reviews?q=دوم", headers=auth(admin)
    )
    assert len(search.json()["data"]["items"]) == 1

    businesses = await client.get(
        "/api/v1/admin/reviews/businesses", headers=auth(admin)
    )
    assert businesses.status_code == 200
    assert businesses.json()["data"]["items"][0]["id"] == str(business.id)
