import sqlalchemy as sa
from datetime import datetime, timezone

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.analytics import QuoteDelivery, SearchLog
from app.models.business import Business, BusinessStatus
from app.models.business_like import BusinessLike
from app.models.category import Category
from app.models.quote import QuoteRequest
from app.models.review import Review
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _seed(db_session, create_user):
    await seed_categories(db_session)
    await db_session.commit()
    category = (await db_session.execute(sa.select(Category))).scalars().first()

    owner = await create_user("09150000001", UserRole.OWNER)
    customer = await create_user("09150000002")
    db_session.add_all(
        [
            Business(
                owner_id=owner.id,
                category_id=category.id,
                name="approved biz",
                slug="approved-biz",
                address="بهبهان",
                status=BusinessStatus.APPROVED,
                rating_avg=4.5,
                rating_count=4,
            ),
            Business(
                owner_id=owner.id,
                category_id=category.id,
                name="pending biz",
                slug="pending-biz",
                address="بهبهان",
                status=BusinessStatus.PENDING,
            ),
            SearchLog(
                query="لوله کش",
                normalized_query="لوله کش",
                category_id=category.id,
                results_count=2,
            ),
            SearchLog(
                query="باغبان",
                normalized_query="باغبان",
                category_id=category.id,
                results_count=0,
            ),
        ]
    )
    await db_session.commit()
    approved = (
        await db_session.execute(
            sa.select(Business).where(Business.slug == "approved-biz")
        )
    ).scalar_one()
    db_session.add(
        Review(
            business_id=approved.id,
            user_id=customer.id,
            rating=5,
            text="عالی",
            status="pending",
            author_name="مشتری",
        )
    )
    await db_session.commit()
    return category


async def test_dashboard_returns_widgets_and_queues(client, db_session, create_user):
    category = await _seed(db_session, create_user)
    admin = await create_user("09150000003", UserRole.SUPERADMIN)

    response = await client.get("/api/v1/admin/dashboard", headers=auth(admin))
    assert response.status_code == 200

    data = response.json()["data"]
    stats = data["stats"]

    assert stats["businesses"]["total"] == 2
    assert stats["businesses"]["approved"] == 1
    assert stats["businesses"]["pending"] == 1
    assert stats["users"]["total"] == 3  # owner + customer + the viewing admin
    assert stats["reviews"]["pending"] == 1
    assert stats["reviews"]["avg_rating"] == 4.5
    assert stats["searches"]["total"] == 2
    assert stats["searches"]["no_result_7d"] == 1

    assert len(data["trend"]) == 14
    assert set(data["trend"][0]) == {"date", "users", "businesses", "reviews", "quotes", "searches"}

    statuses = {row["status"]: row["count"] for row in data["business_status"]}
    assert statuses == {"approved": 1, "pending": 1, "rejected": 0}

    top = {row["id"]: row for row in data["top_categories"]}
    assert top[category.id]["businesses"] == 1
    assert top[category.id]["searches"] == 2

    queues = {row["key"]: row["count"] for row in data["queues"]}
    assert queues["businesses"] == 1
    assert queues["reviews"] == 1
    assert "quotes" in queues


async def test_dashboard_hides_stats_without_permission(client, db_session, create_user):
    await _seed(db_session, create_user)
    admin = await create_user(
        "09150000004", UserRole.ADMIN, permissions=["business.read"]
    )

    response = await client.get("/api/v1/admin/dashboard", headers=auth(admin))
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["stats"] is None
    assert "trend" not in data
    assert "business_status" not in data
    # Only queues covered by the viewer's permissions are returned.
    assert [row["key"] for row in data["queues"]] == ["businesses"]
    assert data["recent_activity"] is not None


async def test_dashboard_requires_authentication(client):
    response = await client.get("/api/v1/admin/dashboard")
    assert response.status_code == 401


async def test_owner_analytics_aggregates_all_businesses(client, db_session, create_user):
    await seed_categories(db_session)
    await db_session.commit()
    category = (await db_session.execute(sa.select(Category))).scalars().first()
    owner = await create_user("09150000010", UserRole.OWNER)
    customer = await create_user("09150000011")

    first = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="اول",
        slug="owner-analytics-1",
        address="بهبهان",
        status=BusinessStatus.APPROVED,
        view_count=7,
        like_count=1,
        rating_avg=4.0,
        rating_count=2,
    )
    second = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="دوم",
        slug="owner-analytics-2",
        address="بهبهان",
        status=BusinessStatus.APPROVED,
        view_count=3,
        like_count=1,
        rating_avg=5.0,
        rating_count=1,
    )
    db_session.add_all([first, second])
    await db_session.commit()
    await db_session.refresh(first)
    await db_session.refresh(second)

    request = QuoteRequest(
        customer_id=customer.id, category_id=category.id, title="نشتی لوله", address="بهبهان"
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    db_session.add_all(
        [
            BusinessLike(user_id=customer.id, business_id=first.id),
            BusinessLike(user_id=owner.id, business_id=second.id),
            QuoteDelivery(request_id=request.id, business_id=first.id),
            QuoteDelivery(
                request_id=request.id,
                business_id=second.id,
                responded_at=datetime.now(timezone.utc),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/me/analytics", headers=auth(owner))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["business_count"] == 2
    assert data["view_count"] == 10
    assert data["like_count"] == 2
    assert data["rating_count"] == 3
    assert data["rating_avg"] == 4.33
    assert data["quote_requests"] == 2
    assert data["quote_responded"] == 1
    assert len(data["series"]) == 30
    assert sum(point["likes"] for point in data["series"]) == 2
    assert sum(point["quotes"] for point in data["series"]) == 2


async def test_owner_analytics_empty_without_business(client, create_user):
    owner = await create_user("09150000012", UserRole.OWNER)
    response = await client.get("/api/v1/me/analytics", headers=auth(owner))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["business_count"] == 0
    assert data["series"] == []
