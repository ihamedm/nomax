from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.notification import Notification
from app.models.quote import Offer, QuoteRequest
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _category(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    return (await db_session.execute(sa.select(Category))).scalars().first()


async def _business(
    db_session,
    owner,
    category,
    *,
    slug="quote-shop",
    is_24h=False,
    geo=(30.638, 50.838),
):
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        name=slug,
        slug=slug,
        address="بهبهان",
        phone_business="09130000000",
        geo_lat=geo[0] if geo else None,
        geo_lng=geo[1] if geo else None,
        is_24h=is_24h,
        status=BusinessStatus.APPROVED,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business


async def _quote(client, customer, category, **overrides):
    body = {
        "title": "تعمیر کولر",
        "category_id": category.id,
        "address": "بهبهان، خیابان شهید بهشتی",
        "geo_lat": 30.638,
        "geo_lng": 50.838,
        **overrides,
    }
    response = await client.post("/api/v1/quotes/requests", json=body, headers=auth(customer))
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_customer_and_owner_quote_views(client, db_session, create_user):
    customer = await create_user("09160000001", full_name="مشتری نمونه")
    owner = await create_user("09160000002", UserRole.OWNER, full_name="مالک نمونه")
    category = await _category(db_session)
    business = await _business(db_session, owner, category)

    quote = await _quote(client, customer, category)
    assert quote["category"]["id"] == category.id
    assert quote["offers_count"] == 0
    assert "customer" not in quote

    mine = await client.get("/api/v1/quotes/requests/mine", headers=auth(customer))
    assert mine.status_code == 200
    assert mine.json()["data"]["items"][0]["id"] == quote["id"]

    incoming = await client.get("/api/v1/quotes/requests/incoming", headers=auth(owner))
    assert incoming.status_code == 200
    payload = incoming.json()["data"]
    assert payload["counts"]["new"] == 1
    item = payload["items"][0]
    assert item["customer"]["name"] == "مشتری نمونه"
    assert "phone" not in item["customer"]
    assert "customer_phone" not in item
    assert item["matching_businesses"] == [{"id": str(business.id), "name": "quote-shop"}]

    offer = await client.post(
        "/api/v1/quotes/offers",
        json={
            "request_id": quote["id"],
            "business_id": str(business.id),
            "price": 2500000,
            "unit": "کل کار",
            "brand": "سامسونگ",
            "message": "فردا مراجعه می‌کنیم.",
        },
        headers=auth(owner),
    )
    assert offer.status_code == 200, offer.text
    offer_id = offer.json()["data"]["id"]

    mine = await client.get("/api/v1/quotes/requests/mine", headers=auth(customer))
    assert mine.json()["data"]["items"][0]["offers_count"] == 1

    archive = await client.get(
        "/api/v1/quotes/requests/incoming?scope=archive", headers=auth(owner)
    )
    assert archive.status_code == 200
    archive_item = archive.json()["data"]["items"][0]
    assert archive_item["my_offer"]["price"] == 2500000
    assert archive_item["my_offer"]["unit"] == "کل کار"
    assert "customer_phone" not in archive.text

    detail = await client.get(f"/api/v1/quotes/{quote['id']}", headers=auth(customer))
    assert detail.status_code == 200
    offers = detail.json()["data"]["offers"]
    assert offers[0]["business"]["name"] == "quote-shop"
    assert "phone_business" not in offers[0]["business"]

    accepted = await client.patch(
        f"/api/v1/quotes/offers/{offer_id}/accept", headers=auth(customer)
    )
    assert accepted.status_code == 200, accepted.text

    mine = await client.get("/api/v1/quotes/requests/mine", headers=auth(customer))
    accepted_quote = mine.json()["data"]["items"][0]
    assert accepted_quote["status"] == "accepted"
    assert accepted_quote["accepted_offer"]["business"]["name"] == "quote-shop"

    customers = await client.get(
        "/api/v1/quotes/requests/incoming?scope=customers", headers=auth(owner)
    )
    assert customers.status_code == 200
    customer_item = customers.json()["data"]["items"][0]
    assert customer_item["customer"]["phone"] == "09160000001"
    assert customer_item["customer_phone"] == "09160000001"

    owner_detail = await client.get(
        f"/api/v1/quotes/{quote['id']}", headers=auth(owner)
    )
    assert owner_detail.json()["data"]["customer_phone"] == "09160000001"

    notifications = (
        await db_session.execute(
            sa.select(Notification)
            .where(Notification.user_id.in_([customer.id, owner.id]))
            .order_by(Notification.created_at)
        )
    ).scalars().all()
    types = {notification.type for notification in notifications}
    assert {"quote_request", "quote_offer", "quote_accepted"} <= types


async def test_offer_validation_and_duplicate(client, db_session, create_user):
    customer = await create_user("09160000011")
    owner = await create_user("09160000012", UserRole.OWNER)
    category = await _category(db_session)
    business = await _business(db_session, owner, category, slug="quote-shop-2")
    quote = await _quote(client, customer, category)

    no_price = await client.post(
        "/api/v1/quotes/offers",
        json={"request_id": quote["id"], "business_id": str(business.id)},
        headers=auth(owner),
    )
    assert no_price.status_code == 422
    assert no_price.json()["error"]["code"] == "invalid_price"

    first = await client.post(
        "/api/v1/quotes/offers",
        json={
            "request_id": quote["id"],
            "business_id": str(business.id),
            "price": 100000,
            "unit": "ساعتی",
        },
        headers=auth(owner),
    )
    assert first.status_code == 200

    duplicate = await client.post(
        "/api/v1/quotes/offers",
        json={
            "request_id": quote["id"],
            "business_id": str(business.id),
            "price": 120000,
        },
        headers=auth(owner),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "offer_already_submitted"


async def test_decline_moves_request_to_archive(client, db_session, create_user):
    customer = await create_user("09160000021")
    owner = await create_user("09160000022", UserRole.OWNER)
    category = await _category(db_session)
    business = await _business(db_session, owner, category, slug="quote-shop-3")
    quote = await _quote(client, customer, category)

    declined = await client.post(
        f"/api/v1/quotes/requests/{quote['id']}/decline",
        json={"business_id": str(business.id)},
        headers=auth(owner),
    )
    assert declined.status_code == 200, declined.text

    new = await client.get(
        "/api/v1/quotes/requests/incoming?scope=new", headers=auth(owner)
    )
    assert new.json()["data"]["items"] == []
    archive = await client.get(
        "/api/v1/quotes/requests/incoming?scope=archive", headers=auth(owner)
    )
    item = archive.json()["data"]["items"][0]
    assert item["id"] == quote["id"]
    assert item["my_offer"]["status"] == "declined"


async def test_unrelated_owner_cannot_open_quote(client, db_session, create_user):
    customer = await create_user("09160000031")
    owner = await create_user("09160000032", UserRole.OWNER)
    other = await create_user("09160000033", UserRole.OWNER)
    category = await _category(db_session)
    await _business(db_session, owner, category, slug="quote-shop-4")
    await _business(db_session, other, category, slug="quote-shop-5")
    quote = await _quote(client, customer, category)

    owner_res = await client.get(f"/api/v1/quotes/{quote['id']}", headers=auth(owner))
    assert owner_res.status_code == 404
    other_res = await client.get(f"/api/v1/quotes/{quote['id']}", headers=auth(other))
    assert other_res.status_code == 404


async def test_cancellation_expires_offer_and_notifies_owner(
    client, db_session, create_user
):
    customer = await create_user("09160000041")
    owner = await create_user("09160000042", UserRole.OWNER)
    category = await _category(db_session)
    business = await _business(db_session, owner, category, slug="quote-shop-6")
    quote = await _quote(client, customer, category)

    offer = await client.post(
        "/api/v1/quotes/offers",
        json={
            "request_id": quote["id"],
            "business_id": str(business.id),
            "price": 500000,
        },
        headers=auth(owner),
    )
    offer_id = offer.json()["data"]["id"]

    cancelled = await client.post(
        f"/api/v1/quotes/requests/{quote['id']}/cancel", headers=auth(customer)
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"

    saved_offer = await db_session.get(Offer, __import__("uuid").UUID(offer_id))
    await db_session.refresh(saved_offer)
    assert saved_offer.status == "expired"

    cancelled_notifications = (
        await db_session.execute(
            sa.select(Notification).where(
                Notification.user_id == owner.id,
                Notification.type == "quote_cancelled",
            )
        )
    ).scalars().all()
    assert len(cancelled_notifications) == 1


async def test_expired_request_is_normalized_on_read(client, db_session, create_user):
    customer = await create_user("09160000051")
    category = await _category(db_session)
    quote = QuoteRequest(
        customer_id=customer.id,
        category_id=category.id,
        title="قدیمی",
        address="بهبهان",
        status="active",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db_session.add(quote)
    await db_session.commit()

    mine = await client.get("/api/v1/quotes/requests/mine", headers=auth(customer))
    assert mine.status_code == 200
    assert mine.json()["data"]["items"][0]["status"] == "expired"


async def test_admin_quote_dashboard(client, db_session, create_user):
    customer = await create_user("09160000061", full_name="خریدار ادمین")
    owner = await create_user("09160000062", UserRole.OWNER)
    admin = await create_user(
        "09160000063", UserRole.ADMIN, permissions=["quote.read"]
    )
    manager = await create_user(
        "09160000064", UserRole.ADMIN, permissions=["quote.read", "quote.manage"]
    )
    category = await _category(db_session)
    business = await _business(db_session, owner, category, slug="quote-shop-7")
    quote = await _quote(client, customer, category)
    await client.post(
        "/api/v1/quotes/offers",
        json={
            "request_id": quote["id"],
            "business_id": str(business.id),
            "price": 700000,
        },
        headers=auth(owner),
    )

    stats = await client.get("/api/v1/admin/quotes/stats", headers=auth(admin))
    assert stats.status_code == 200, stats.text
    assert stats.json()["data"]["total"] == 1
    assert stats.json()["data"]["offers_total"] == 1
    assert stats.json()["data"]["acceptance_rate"] == 0

    listed = await client.get("/api/v1/admin/quotes", headers=auth(admin))
    assert listed.status_code == 200
    item = listed.json()["data"]["items"][0]
    assert item["customer"]["phone"] == "09160000061"
    assert item["offers_count"] == 1

    detail = await client.get(
        f"/api/v1/admin/quotes/{quote['id']}", headers=auth(admin)
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["offers"][0]["price"] == 700000

    forbidden = await client.post(
        f"/api/v1/admin/quotes/{quote['id']}/cancel", headers=auth(admin)
    )
    assert forbidden.status_code == 403

    cancelled = await client.post(
        f"/api/v1/admin/quotes/{quote['id']}/cancel", headers=auth(manager)
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"


async def test_geo_radius_filters_incoming(
    client, db_session, create_user, set_dispatch_settings
):
    customer = await create_user("09160000071")
    owner = await create_user("09160000072", UserRole.OWNER)
    category = await _category(db_session)
    # Disable the category-wide distance fallback for this test; the default
    # intentionally reaches far owners rather than losing the request.
    await set_dispatch_settings(fallback_outside_radius=False, expand_radius_km=10)
    await _business(db_session, owner, category, slug="far-shop", geo=(31.5, 51.5))
    await _quote(client, customer, category, geo_lat=30.638, geo_lng=50.838)

    incoming = await client.get(
        "/api/v1/quotes/requests/incoming", headers=auth(owner)
    )
    assert incoming.json()["data"]["items"] == []


async def test_normal_request_not_dispatched_at_night(db_session, create_user, set_dispatch_settings):
    from app.services.quote_dispatcher import dispatch_quote

    await set_dispatch_settings(day_start_hour=6, day_end_hour=21)
    customer = await create_user("09160000081")
    owner = await create_user("09160000082", UserRole.OWNER)
    category = await _category(db_session)
    await _business(db_session, owner, category, slug="night-shop", is_24h=True)
    quote = QuoteRequest(
        customer_id=customer.id,
        category_id=category.id,
        title="عادی",
        address="بهبهان",
        is_urgent=False,
    )
    db_session.add(quote)
    await db_session.commit()
    await db_session.refresh(quote)

    targeted = await dispatch_quote(
        db_session, quote, now=datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc)
    )
    assert targeted == []
    notifications = (
        await db_session.execute(sa.select(Notification))
    ).scalars().all()
    assert notifications == []
