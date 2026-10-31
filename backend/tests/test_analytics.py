import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.analytics import QuoteDelivery, SearchLog
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.quote import Offer, QuoteRequest
from app.models.review import Review
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _seed(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    category = (
        await db_session.execute(
            sa.select(Category).where(Category.slug == "repairs")
        )
    ).scalars().first()
    subcategory = (
        await db_session.execute(
            sa.select(Subcategory).where(
                Subcategory.category_id == category.id,
                Subcategory.slug == "home_appliance",
            )
        )
    ).scalars().first()
    return category, subcategory


async def _business(db_session, owner, category, subcategory, *, slug, status=BusinessStatus.APPROVED):
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        subcategory_id=subcategory.id,
        name=slug,
        slug=slug,
        address="بهبهان",
        geo_lat=30.638,
        geo_lng=50.838,
        status=status,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business


async def test_search_logging_and_analytics_dashboard(client, db_session, create_user):
    category, subcategory = await _seed(db_session)
    owner = await create_user("09171000001", UserRole.OWNER, full_name="مالک تحلیل")
    customer = await create_user("09171000002", full_name="مشتری تحلیل")
    reviewer = await create_user("09171000003", full_name="نویسنده")
    pending_customer = await create_user("09171000004", full_name="مشتری دوم")
    admin = await create_user(
        "09171000005", UserRole.ADMIN, permissions=["stats.read"]
    )
    business = await _business(
        db_session, owner, category, subcategory, slug="تحلیل تعمیرگاه"
    )
    await _business(
        db_session,
        owner,
        category,
        subcategory,
        slug="تحلیل کسب‌وکار در انتظار",
        status=BusinessStatus.PENDING,
    )

    db_session.add(
        Review(
            business_id=business.id,
            user_id=reviewer.id,
            rating=4,
            text="نظر در انتظار",
            status="pending",
        )
    )
    await db_session.commit()

    # Search logging: one with results, one without.
    found = await client.get(
        "/api/v1/businesses",
        params={
            "q": "تعمیر",
            "cat": "repairs",
            "subcat": "home_appliance",
            "lat": 30.638,
            "lng": 50.838,
            "limit": 12,
        },
    )
    assert found.status_code == 200
    empty = await client.get(
        "/api/v1/businesses",
        params={"q": "قطعه‌ناموجود", "lat": 30.638, "lng": 50.838, "limit": 12},
    )
    assert empty.status_code == 200
    logs = (await db_session.execute(sa.select(SearchLog))).scalars().all()
    assert len(logs) == 2
    assert {log.normalized_query for log in logs} == {"تعمیر", "قطعه‌ناموجود"}
    assert any(log.results_count == 0 for log in logs)
    assert any(log.category_id == category.id for log in logs)

    # Quote request → delivery → owner sees it → offer → customer accepts.
    quote_response = await client.post(
        "/api/v1/quotes/requests",
        json={
            "title": "تعمیر لباسشویی",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان، خیابان شهید بهشتی",
            "geo_lat": 30.638,
            "geo_lng": 50.838,
        },
        headers=auth(customer),
    )
    assert quote_response.status_code == 200, quote_response.text
    quote_id = quote_response.json()["data"]["id"]

    deliveries = (
        await db_session.execute(
            sa.select(QuoteDelivery).where(QuoteDelivery.request_id == __import__("uuid").UUID(quote_id))
        )
    ).scalars().all()
    assert len(deliveries) == 1

    incoming = await client.get(
        "/api/v1/quotes/requests/incoming", headers=auth(owner)
    )
    assert incoming.status_code == 200
    await db_session.refresh(deliveries[0])
    assert deliveries[0].seen_at is not None

    offer = await client.post(
        "/api/v1/quotes/offers",
        json={
            "request_id": quote_id,
            "business_id": str(business.id),
            "price": 1200000,
            "unit": "کل کار",
        },
        headers=auth(owner),
    )
    assert offer.status_code == 200, offer.text
    offer_id = offer.json()["data"]["id"]
    accepted = await client.patch(
        f"/api/v1/quotes/offers/{offer_id}/accept", headers=auth(customer)
    )
    assert accepted.status_code == 200, accepted.text
    saved_quote = await db_session.get(QuoteRequest, __import__("uuid").UUID(quote_id))
    await db_session.refresh(saved_quote)
    assert saved_quote.accepted_at is not None

    # A second active quote with no response keeps the "needs action" count > 0.
    waiting = await client.post(
        "/api/v1/quotes/requests",
        json={
            "title": "تعمیر یخچال",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان، بلوار آزادی",
            "geo_lat": 30.638,
            "geo_lng": 50.838,
        },
        headers=auth(pending_customer),
    )
    assert waiting.status_code == 200
    await client.get("/api/v1/quotes/requests/incoming", headers=auth(owner))

    overview = await client.get("/api/v1/admin/analytics/overview", headers=auth(admin))
    assert overview.status_code == 200, overview.text
    data = overview.json()["data"]
    assert data["widgets"]["businesses_total"] == 2
    assert data["widgets"]["searches_total"] == 2
    assert data["widgets"]["quotes_total"] == 2
    assert data["pending"]["businesses"] == 1
    assert data["pending"]["reviews"] == 1
    assert data["pending"]["quotes"] == 1
    assert data["pending"]["total"] == 3
    assert len(data["daily"]) == 14
    assert len(data["hourly"]) == 24
    assert sum(row["searches"] for row in data["daily"]) == 2
    assert sum(row["quote_requests"] for row in data["daily"]) == 2
    assert data["roles"][0]["role"] == "customer"
    assert data["roles"][0]["count"] >= 3
    today = next(item for item in data["quote_funnel"] if item["range"] == "today")
    assert today["counts"]["requests"] == 2
    assert today["counts"]["sent"] == 2
    assert today["counts"]["seen"] == 2
    assert today["counts"]["responded"] == 1
    assert today["counts"]["chosen"] == 1

    quotes = await client.get("/api/v1/admin/analytics/quotes", headers=auth(admin))
    assert quotes.status_code == 200, quotes.text
    qdata = quotes.json()["data"]
    assert qdata["widgets"]["total"] == 2
    assert qdata["widgets"]["accepted"] == 1
    assert qdata["widgets"]["offers_total"] == 1
    assert qdata["widgets"]["response_rate"] == 50
    statuses = {item["status"]: item["count"] for item in qdata["statuses"]}
    assert statuses == {"active": 1, "accepted": 1, "cancelled": 0, "expired": 0}
    timing = {item["key"]: item for item in qdata["timings"]}
    assert timing["offer"]["avg_seconds"] is not None
    assert timing["choice"]["avg_seconds"] is not None
    assert timing["seen"]["count"] == 2

    market = await client.get("/api/v1/admin/analytics/market", headers=auth(admin))
    assert market.status_code == 200, market.text
    mdata = market.json()["data"]
    row = next(item for item in mdata["categories"] if item["id"] == category.id)
    assert row["businesses"] == 1
    assert row["searches"] == 1
    assert row["quotes"] == 2
    assert row["unanswered_quotes"] == 1
    assert row["demand"] == 3
    assert row["status"] in {"urgent", "shortage", "balanced", "surplus", "no_demand", "no_supply"}
    keywords = {item["keyword"]: item for item in mdata["keywords"]}
    assert keywords["تعمیر"]["searches"] == 1
    no_result = {item["keyword"]: item for item in mdata["no_result_keywords"]}
    assert no_result["قطعه‌ناموجود"]["searches"] == 1

    performance = await client.get(
        "/api/v1/admin/analytics/businesses", headers=auth(admin)
    )
    assert performance.status_code == 200, performance.text
    perf_items = performance.json()["data"]["items"]
    assert len(perf_items) == 1
    assert perf_items[0]["quotes_suggested"] == 1
    assert perf_items[0]["quotes_accepted"] == 1
    assert perf_items[0]["response_rate"] == 50
    assert perf_items[0]["negative_rate"] == 0

    map_response = await client.get("/api/v1/admin/analytics/map", headers=auth(admin))
    assert map_response.status_code == 200, map_response.text
    map_items = map_response.json()["data"]
    assert len(map_items["businesses"]) == 1
    assert len(map_items["quotes"]) == 1
    assert map_items["urgent_quotes"] == []

    logs = await client.get(
        "/api/v1/admin/analytics/logs?per_page=5", headers=auth(admin)
    )
    assert logs.status_code == 200, logs.text
    log_data = logs.json()
    assert log_data["meta"]["per_page"] == 5
    assert len(log_data["data"]["items"]) == 5
    assert log_data["meta"]["total"] >= 15
    assert log_data["meta"]["pages"] >= 3
    event_types = {item["type"] for item in log_data["data"]["items"]}
    assert len(event_types) >= 2

    search_logs = await client.get(
        "/api/v1/admin/analytics/logs?type=search", headers=auth(admin)
    )
    assert search_logs.status_code == 200
    assert search_logs.json()["meta"]["total"] == 2
    assert all(
        item["type"] == "search" for item in search_logs.json()["data"]["items"]
    )

    summary = await client.get(
        "/api/v1/admin/analytics/logs/summary", headers=auth(admin)
    )
    assert summary.status_code == 200, summary.text
    summary_data = summary.json()["data"]
    assert len(summary_data["daily"]) == 14
    by_type = {item["type"]: item["count"] for item in summary_data["by_type"]}
    assert by_type["search"] == 2
    assert summary_data["total"] >= 15


async def test_analytics_requires_stats_permission(client, create_user):
    admin = await create_user("09171000011", UserRole.ADMIN, permissions=[])
    response = await client.get("/api/v1/admin/analytics/overview", headers=auth(admin))
    assert response.status_code == 403


async def test_empty_analytics_payloads(client, create_user):
    admin = await create_user(
        "09171000021", UserRole.ADMIN, permissions=["stats.read"]
    )
    for path in (
        "/api/v1/admin/analytics/overview",
        "/api/v1/admin/analytics/quotes",
        "/api/v1/admin/analytics/market",
        "/api/v1/admin/analytics/businesses",
        "/api/v1/admin/analytics/map",
        "/api/v1/admin/analytics/logs",
        "/api/v1/admin/analytics/logs/summary",
    ):
        response = await client.get(path, headers=auth(admin))
        assert response.status_code == 200, response.text
        assert response.json()["data"]
