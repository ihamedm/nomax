import pytest
import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.quote import QuoteRequest
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _category(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    return (await db_session.execute(sa.select(Category))).scalars().first()


async def test_only_one_active_request(client, db_session, create_user):
    customer = await create_user("09120000001")
    category = await _category(db_session)
    body = {"title": "نشتی لوله", "category_id": category.id, "address": "بهبهان"}
    first = await client.post("/api/v1/quotes/requests", json=body, headers=auth(customer))
    assert first.status_code == 200
    second = await client.post("/api/v1/quotes/requests", json=body, headers=auth(customer))
    assert second.status_code == 409


async def test_urgent_expiry_is_two_hours(client, db_session, create_user):
    customer = await create_user("09120000002")
    category = await _category(db_session)
    response = await client.post(
        "/api/v1/quotes/requests",
        json={"title": "فوری", "category_id": category.id, "address": "بهبهان", "is_urgent": True},
        headers=auth(customer),
    )
    assert response.status_code == 200
    quote = await db_session.get(QuoteRequest, __import__("uuid").UUID(response.json()["data"]["id"]))
    delta = quote.expires_at.timestamp() - quote.created_at.timestamp()
    assert 7000 < delta < 7400


async def test_my_quotes_lists_only_own_requests(client, db_session, create_user):
    customer = await create_user("09120000011")
    other = await create_user("09120000012")
    category = await _category(db_session)
    created = await client.post(
        "/api/v1/quotes/requests",
        json={"title": "تعمیر", "category_id": category.id, "address": "بهبهان"},
        headers=auth(customer),
    )
    assert created.status_code == 200

    mine = await client.get("/api/v1/quotes/requests/mine", headers=auth(customer))
    assert mine.status_code == 200
    items = mine.json()["data"]["items"]
    assert [item["id"] for item in items] == [created.json()["data"]["id"]]
    assert "customer_phone" not in mine.text

    empty = await client.get("/api/v1/quotes/requests/mine", headers=auth(other))
    assert empty.json()["data"]["items"] == []


async def test_phone_revealed_only_after_acceptance(client, db_session, create_user):
    customer = await create_user("09120000003")
    owner = await create_user("09120000004", UserRole.OWNER)
    other = await create_user("09120000005", UserRole.OWNER)
    category = await _category(db_session)

    for slug, user in (("biz-a", owner), ("biz-b", other)):
        db_session.add(
            Business(
                owner_id=user.id,
                category_id=category.id,
                name=slug,
                slug=slug,
                address="بهبهان",
                status=BusinessStatus.APPROVED,
            )
        )
    await db_session.commit()

    quote_res = await client.post(
        "/api/v1/quotes/requests",
        json={"title": "تعمیر", "category_id": category.id, "address": "بهبهان"},
        headers=auth(customer),
    )
    quote_id = quote_res.json()["data"]["id"]

    # Owner view never includes the customer phone.
    incoming = await client.get("/api/v1/quotes/requests/incoming", headers=auth(owner))
    assert "customer_phone" not in incoming.text

    business = (
        await db_session.execute(sa.select(Business).where(Business.owner_id == owner.id))
    ).scalars().first()
    offer_res = await client.post(
        "/api/v1/quotes/offers",
        json={"request_id": quote_id, "business_id": str(business.id), "price": 100000},
        headers=auth(owner),
    )
    assert offer_res.status_code == 200
    offer_id = offer_res.json()["data"]["id"]

    accept = await client.patch(
        f"/api/v1/quotes/offers/{offer_id}/accept", headers=auth(customer)
    )
    assert accept.status_code == 200

    detail = await client.get(f"/api/v1/quotes/{quote_id}", headers=auth(owner))
    assert detail.json()["data"]["customer_phone"] == "09120000003"

    # The other business never gets the phone.
    other_detail = await client.get(f"/api/v1/quotes/{quote_id}", headers=auth(other))
    assert "customer_phone" not in other_detail.text


async def test_offer_rejected_for_expired_request(client, db_session, create_user):
    from datetime import datetime, timedelta, timezone

    customer = await create_user("09120000006")
    owner = await create_user("09120000007", UserRole.OWNER)
    category = await _category(db_session)
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="biz",
        slug="biz-exp",
        address="بهبهان",
        status=BusinessStatus.APPROVED,
    )
    db_session.add(business)
    quote = QuoteRequest(
        customer_id=customer.id,
        category_id=category.id,
        title="قدیمی",
        address="بهبهان",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(quote)
    await db_session.commit()
    await db_session.refresh(quote)

    response = await client.post(
        "/api/v1/quotes/offers",
        json={"request_id": str(quote.id), "business_id": str(business.id)},
        headers=auth(owner),
    )
    assert response.status_code == 409


async def test_dispatch_night_only_targets_24h_businesses(
    db_session, create_user, set_dispatch_settings
):
    from datetime import datetime, timezone

    from app.services.quote_dispatcher import dispatch_quote

    await set_dispatch_settings(day_start_hour=6, day_end_hour=21)
    customer = await create_user("09120000008")
    day_owner = await create_user("09120000009", UserRole.OWNER)
    night_owner = await create_user("09120000010", UserRole.OWNER)
    category = await _category(db_session)

    db_session.add_all(
        [
            Business(owner_id=day_owner.id, category_id=category.id, name="day", slug="day",
                     address="بهبهان", status=BusinessStatus.APPROVED, is_24h=False),
            Business(owner_id=night_owner.id, category_id=category.id, name="night", slug="night",
                     address="بهبهان", status=BusinessStatus.APPROVED, is_24h=True),
        ]
    )
    quote = QuoteRequest(customer_id=customer.id, category_id=category.id, title="شب",
                         address="بهبهان", is_urgent=True)
    db_session.add(quote)
    await db_session.commit()
    await db_session.refresh(quote)

    targeted = await dispatch_quote(db_session, quote, now=datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc))
    assert [b.slug for b in targeted] == ["night"]
