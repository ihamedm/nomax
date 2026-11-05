import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.analytics import SearchLog
from app.models.business import Business, BusinessStatus
from app.models.category import Category
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
