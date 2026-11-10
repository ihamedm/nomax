from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.analytics import QuoteDelivery
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.notification import Notification
from app.models.quote import QuoteRequest
from app.models.user import UserRole
from app.services import quote_broker
from app.services.quote_dispatcher import dispatch_quote, retry_due_quote
from app.services.quote_service import ACTIVE


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _category(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    return (await db_session.execute(sa.select(Category).order_by(Category.id))).scalars().first()


async def _business(
    db_session,
    owner,
    category,
    *,
    slug,
    subcategory_id=None,
    is_24h=False,
    geo=None,
    status=BusinessStatus.APPROVED,
):
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        subcategory_id=subcategory_id,
        name=slug,
        slug=slug,
        address="بهبهان",
        phone_business="09130000000",
        is_24h=is_24h,
        geo_lat=geo[0] if geo else None,
        geo_lng=geo[1] if geo else None,
        status=status,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business


async def _quote_row(db_session, customer, category, **overrides):
    quote = QuoteRequest(
        customer_id=customer.id,
        category_id=category.id,
        title=overrides.pop("title", "تعمیر کولر"),
        address="بهبهان، خیابان شهید بهشتی",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        status=ACTIVE,
        **overrides,
    )
    db_session.add(quote)
    await db_session.commit()
    await db_session.refresh(quote)
    return quote


async def test_subcategory_fallback_reaches_parent_category_owner(
    client, db_session, create_user, set_dispatch_settings
):
    customer = await create_user("09170000001")
    owner = await create_user("09170000002", UserRole.OWNER)
    category = await _category(db_session)
    subcategories = (
        await db_session.execute(
            sa.select(Subcategory)
            .where(Subcategory.category_id == category.id)
            .order_by(Subcategory.id)
            .limit(2)
        )
    ).scalars().all()
    assert len(subcategories) >= 2
    await _business(
        db_session,
        owner,
        category,
        slug="parent-category-shop",
        subcategory_id=subcategories[1].id,
    )

    response = await client.post(
        "/api/v1/quotes/requests",
        json={
            "title": "تعمیر یخچال",
            "category_id": category.id,
            "subcategory_id": subcategories[0].id,
            "address": "بهبهان، خیابان شهید بهشتی",
        },
        headers=auth(customer),
    )
    assert response.status_code == 200, response.text
    quote = response.json()["data"]
    assert quote["dispatch"]["delivered_count"] == 1
    assert quote["dispatch"]["state"] == "waiting_seen"

    deliveries = (
        await db_session.execute(
            sa.select(QuoteDelivery).where(
                QuoteDelivery.request_id == __import__("uuid").UUID(quote["id"])
            )
        )
    ).scalars().all()
    assert len(deliveries) == 1

    notifications = (
        await db_session.execute(
            sa.select(Notification).where(Notification.user_id == owner.id)
        )
    ).scalars().all()
    assert any(item.type == "quote_request" for item in notifications)

    incoming = await client.get(
        "/api/v1/quotes/requests/incoming", headers=auth(owner)
    )
    assert incoming.status_code == 200
    items = incoming.json()["data"]["items"]
    assert [item["id"] for item in items] == [quote["id"]]
    assert items[0]["matching_businesses"][0]["name"] == "parent-category-shop"

    offer = await client.post(
        "/api/v1/quotes/offers",
        json={
            "request_id": quote["id"],
            "business_id": items[0]["matching_businesses"][0]["id"],
            "price": 900000,
        },
        headers=auth(owner),
    )
    assert offer.status_code == 200, offer.text


async def test_quiet_hours_are_tehran_local_and_schedule_morning(
    db_session, create_user, set_dispatch_settings
):
    await set_dispatch_settings(day_start_hour=6, day_end_hour=21)
    customer = await create_user("09170000011")
    owner = await create_user("09170000012", UserRole.OWNER)
    category = await _category(db_session)
    await _business(db_session, owner, category, slug="morning-shop")
    quote = await _quote_row(db_session, customer, category)

    targeted = await dispatch_quote(
        db_session,
        quote,
        now=datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc),
    )
    await db_session.commit()
    assert targeted == []
    assert quote.dispatch_status == "scheduled"
    next_at = quote.next_dispatch_at
    if next_at.tzinfo is None:
        next_at = next_at.replace(tzinfo=timezone.utc)
    local = next_at.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Tehran"))
    assert (local.hour, local.minute) == (6, 0)
    assert local.day == 2


async def test_urgent_night_without_24h_owner_falls_back(
    db_session, create_user, set_dispatch_settings
):
    await set_dispatch_settings(day_start_hour=6, day_end_hour=21)
    customer = await create_user("09170000021")
    owner = await create_user("09170000022", UserRole.OWNER)
    category = await _category(db_session)
    business = await _business(db_session, owner, category, slug="not-24h")
    quote = await _quote_row(db_session, customer, category, is_urgent=True)

    targeted = await dispatch_quote(
        db_session,
        quote,
        now=datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc),
    )
    assert [item.id for item in targeted] == [business.id]
    assert quote.dispatch_round == 1


async def test_waves_expand_to_new_owners_until_max_rounds(
    db_session, create_user, set_dispatch_settings
):
    await set_dispatch_settings(
        initial_batch_size=2,
        retry_batch_size=2,
        min_target_deliveries=2,
        max_rounds=3,
        response_window_minutes=5,
    )
    customer = await create_user("09170000031")
    category = await _category(db_session)
    for index in range(5):
        owner = await create_user(f"0917000004{index}", UserRole.OWNER)
        await _business(db_session, owner, category, slug=f"wave-shop-{index}")
    quote = await _quote_row(db_session, customer, category)
    now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    await dispatch_quote(db_session, quote, now=now)
    await db_session.commit()
    assert quote.dispatch_round == 1
    count = (
        await db_session.execute(
            sa.select(sa.func.count(QuoteDelivery.id)).where(
                QuoteDelivery.request_id == quote.id
            )
        )
    ).scalar()
    assert count == 2

    delivered_ids: set = set()
    for step in range(2):
        quote.next_dispatch_at = now - timedelta(seconds=1)
        await db_session.commit()
        now = now + timedelta(minutes=6)
        await retry_due_quote(db_session, quote, now=now)
        await db_session.commit()
        rows = (
            await db_session.execute(
                sa.select(QuoteDelivery).where(QuoteDelivery.request_id == quote.id)
            )
        ).scalars().all()
        assert len(rows) == min(5, 2 * (step + 2))
        delivered_ids = {row.business_id for row in rows}

    assert len(delivered_ids) == 5
    assert quote.dispatch_round == 3
    assert quote.dispatch_status == "exhausted"
    assert quote.next_dispatch_at is None


async def test_seen_without_offer_waits_when_toggle_is_off(
    db_session, create_user, set_dispatch_settings
):
    await set_dispatch_settings(
        initial_batch_size=2,
        retry_batch_size=2,
        min_target_deliveries=2,
        max_rounds=5,
        advance_on_seen=False,
    )
    customer = await create_user("09170000051")
    category = await _category(db_session)
    for index in range(4):
        owner = await create_user(f"0917000006{index}", UserRole.OWNER)
        await _business(db_session, owner, category, slug=f"seen-shop-{index}")
    quote = await _quote_row(db_session, customer, category)
    now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    await dispatch_quote(db_session, quote, now=now)
    await db_session.commit()

    deliveries = (
        await db_session.execute(
            sa.select(QuoteDelivery).where(QuoteDelivery.request_id == quote.id)
        )
    ).scalars().all()
    for delivery in deliveries:
        delivery.seen_at = now
    quote.next_dispatch_at = now - timedelta(seconds=1)
    await db_session.commit()

    targeted = await retry_due_quote(db_session, quote, now=now + timedelta(minutes=6))
    await db_session.commit()
    assert targeted == []
    assert quote.dispatch_round == 1
    assert quote.next_dispatch_at is not None

    await set_dispatch_settings(
        initial_batch_size=2,
        retry_batch_size=2,
        min_target_deliveries=2,
        max_rounds=5,
        advance_on_seen=True,
    )
    quote.next_dispatch_at = now - timedelta(seconds=1)
    await db_session.commit()
    targeted = await retry_due_quote(db_session, quote, now=now + timedelta(minutes=12))
    await db_session.commit()
    assert len(targeted) == 2
    assert quote.dispatch_round == 2


async def test_no_candidate_quote_is_recovered_after_business_appears(
    db_session, create_user, set_dispatch_settings
):
    await set_dispatch_settings(
        no_candidate_retry_minutes=10, initial_batch_size=2, min_target_deliveries=2
    )
    customer = await create_user("09170000071")
    owner = await create_user("09170000072", UserRole.OWNER)
    category = await _category(db_session)
    quote = await _quote_row(db_session, customer, category)
    now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    await dispatch_quote(db_session, quote, now=now)
    await db_session.commit()
    assert quote.dispatch_round == 0
    assert quote.dispatch_status == "searching"
    assert quote.next_dispatch_at is not None

    business = await _business(db_session, owner, category, slug="late-shop")
    quote.next_dispatch_at = now - timedelta(seconds=1)
    await db_session.commit()
    targeted = await retry_due_quote(db_session, quote, now=now + timedelta(minutes=11))
    await db_session.commit()
    assert [item.id for item in targeted] == [business.id]
    assert quote.dispatch_round == 1


async def test_worker_reconciles_due_quote_and_advances_wave(
    db_session, create_user, set_dispatch_settings, monkeypatch
):
    from app.worker import _process_quote_ids

    await set_dispatch_settings(
        initial_batch_size=1,
        retry_batch_size=1,
        min_target_deliveries=1,
        max_rounds=4,
    )
    customer = await create_user("09170000081")
    category = await _category(db_session)
    for index in range(2):
        owner = await create_user(f"0917000009{index}", UserRole.OWNER)
        await _business(db_session, owner, category, slug=f"worker-shop-{index}")
    quote = await _quote_row(db_session, customer, category)
    now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    await dispatch_quote(db_session, quote, now=now)
    quote.next_dispatch_at = now - timedelta(seconds=1)
    await db_session.commit()

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(quote_broker, "schedule_retry", _noop)
    monkeypatch.setattr(quote_broker, "clear_retry", _noop)
    processed = await _process_quote_ids(db_session, [quote.id], now + timedelta(minutes=6))
    assert processed == 1
    count = (
        await db_session.execute(
            sa.select(sa.func.count(QuoteDelivery.id)).where(
                QuoteDelivery.request_id == quote.id
            )
        )
    ).scalar()
    assert count == 2


async def test_admin_manual_assignment_is_audited_and_idempotent(
    client, db_session, create_user, set_dispatch_settings
):
    admin = await create_user("09170000101", UserRole.SUPERADMIN)
    customer = await create_user("09170000102")
    owner = await create_user("09170000103", UserRole.OWNER)
    categories = (
        await db_session.execute(sa.select(Category).order_by(Category.id).limit(2))
    ).scalars().all()
    if len(categories) < 2:
        await _category(db_session)
        categories = (
            await db_session.execute(sa.select(Category).order_by(Category.id).limit(2))
        ).scalars().all()
    quote_category, other_category = categories[0], categories[1]
    business = await _business(
        db_session, owner, other_category, slug="manual-unrelated-shop"
    )
    quote = await _quote_row(db_session, customer, quote_category)
    now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    await dispatch_quote(db_session, quote, now=now)
    await db_session.commit()

    assigned = await client.post(
        f"/api/v1/admin/quotes/{quote.id}/assign",
        json={"business_ids": [str(business.id)]},
        headers=auth(admin),
    )
    assert assigned.status_code == 200, assigned.text
    payload = assigned.json()["data"]
    assert [item["id"] for item in payload["assigned"]] == [str(business.id)]
    assert payload["summary"]["delivered_count"] == 1
    assert payload["deliveries"][0]["source"] == "manual"
    assert payload["deliveries"][0]["owner"]["phone"] == owner.phone

    duplicate = await client.post(
        f"/api/v1/admin/quotes/{quote.id}/assign",
        json={"business_ids": [str(business.id)]},
        headers=auth(admin),
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["data"]["assigned"] == []
    assert duplicate.json()["data"]["skipped"] == [str(business.id)]

    detail = await client.get(
        f"/api/v1/admin/quotes/{quote.id}/dispatch", headers=auth(admin)
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["summary"]["delivered_count"] == 1

    notifications = (
        await db_session.execute(
            sa.select(Notification).where(Notification.user_id == owner.id)
        )
    ).scalars().all()
    assert len([item for item in notifications if item.type == "quote_request"]) == 1


async def test_customer_dispatch_summary_and_settings_api(
    client, db_session, create_user, set_dispatch_settings
):
    await set_dispatch_settings(day_start_hour=6, day_end_hour=21)
    admin = await create_user("09170000111", UserRole.SUPERADMIN)
    customer = await create_user("09170000112")
    owner = await create_user("09170000113", UserRole.OWNER)
    category = await _category(db_session)
    await _business(db_session, owner, category, slug="summary-shop")
    quote = await _quote_row(db_session, customer, category)
    now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    await dispatch_quote(db_session, quote, now=now)
    await db_session.commit()

    mine = await client.get("/api/v1/quotes/requests/mine", headers=auth(customer))
    dispatch = mine.json()["data"]["items"][0]["dispatch"]
    assert dispatch["delivered_count"] == 1
    assert dispatch["max_rounds"] >= 1
    assert "business" not in dispatch
    assert "next_dispatch_at" in dispatch

    settings = await client.get("/api/v1/admin/settings", headers=auth(admin))
    assert settings.status_code == 200
    assert settings.json()["data"]["quote_dispatch"]["enabled"] is True

    updated = await client.put(
        "/api/v1/admin/settings/quote_dispatch",
        json={
            "value": {
                "initial_batch_size": 4,
                "advance_on_seen": False,
                "response_window_minutes": 35,
            }
        },
        headers=auth(admin),
    )
    assert updated.status_code == 200, updated.text
    value = updated.json()["data"]["value"]
    assert value["initial_batch_size"] == 4
    assert value["advance_on_seen"] is False
    assert value["response_window_minutes"] == 35
    assert value["day_start_hour"] == 6

    invalid = await client.put(
        "/api/v1/admin/settings/quote_dispatch",
        json={"value": {"day_start_hour": 22, "day_end_hour": 6}},
        headers=auth(admin),
    )
    assert invalid.status_code == 422
