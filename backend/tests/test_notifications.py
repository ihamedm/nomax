"""In-app message center: rejection messages, unread badges and announcements."""

import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.notification import Notification
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _setup(db_session, create_user):
    await seed_categories(db_session)
    await db_session.commit()
    category = (await db_session.execute(sa.select(Category))).scalars().first()
    owner = await create_user("09150000001", UserRole.OWNER)
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="کافه تست",
        slug="cafe-notify",
        address="بهبهان",
        status=BusinessStatus.PENDING,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return owner, business


async def _reject(client, business, admin, reason="مدرک ناقص"):
    return await client.patch(
        f"/api/v1/admin/businesses/{business.id}/reject",
        json={"reason": reason},
        headers=auth(admin),
    )


async def test_rejection_sends_message_to_owner(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    admin = await create_user("09150000002", UserRole.ADMIN, permissions=["business.approve"])

    response = await _reject(client, business, admin, "عکس واضح نیست")
    assert response.status_code == 200

    notification = (
        await db_session.execute(sa.select(Notification))
    ).scalars().one()
    assert notification.user_id == owner.id
    assert notification.type == "business_rejected"
    assert "رد شد" in notification.title
    assert "عکس واضح نیست" in notification.body
    assert notification.payload["business_id"] == str(business.id)
    assert notification.payload["rejection_reason"] == "عکس واضح نیست"
    assert notification.payload["action_url"] == f"/businesses/{business.id}/edit"
    assert notification.is_read is False

    inbox = await client.get("/api/v1/me/notifications", headers=auth(owner))
    assert inbox.status_code == 200
    body = inbox.json()["data"]
    assert body["unread_count"] == 1
    assert body["items"][0]["type"] == "business_rejected"
    assert body["items"][0]["payload"]["business_id"] == str(business.id)

    count = await client.get("/api/v1/me/notifications/unread-count", headers=auth(owner))
    assert count.status_code == 200
    assert count.json()["data"]["count"] == 1

    read = await client.patch(
        f"/api/v1/notifications/{notification.id}/read", headers=auth(owner)
    )
    assert read.status_code == 200
    assert read.json()["data"]["unread_count"] == 0

    count = await client.get("/api/v1/me/notifications/unread-count", headers=auth(owner))
    assert count.json()["data"]["count"] == 0


async def test_reject_requires_reason(client, db_session, create_user):
    _, business = await _setup(db_session, create_user)
    admin = await create_user("09150000003", UserRole.ADMIN, permissions=["business.approve"])
    response = await client.patch(
        f"/api/v1/admin/businesses/{business.id}/reject",
        json={"reason": "   "},
        headers=auth(admin),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "rejection_reason_required"
    assert (await db_session.execute(sa.select(Notification))).scalars().first() is None


async def test_approval_sends_message_and_read_all_clears_badge(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    admin = await create_user("09150000004", UserRole.ADMIN, permissions=["business.approve"])

    await _reject(client, business, admin)
    approved = await client.patch(
        f"/api/v1/admin/businesses/{business.id}/approve", headers=auth(admin)
    )
    assert approved.status_code == 200

    notifications = (await db_session.execute(sa.select(Notification))).scalars().all()
    assert len(notifications) == 2
    assert {item.type for item in notifications} == {
        "business_rejected",
        "business_approved",
    }
    approved_message = next(item for item in notifications if item.type == "business_approved")
    assert approved_message.payload["business_slug"] == business.slug
    assert approved_message.payload["action_url"] == f"/businesses/{business.slug}"

    count = await client.get("/api/v1/me/notifications/unread-count", headers=auth(owner))
    assert count.json()["data"]["count"] == 2

    read_all = await client.patch("/api/v1/me/notifications/read-all", headers=auth(owner))
    assert read_all.status_code == 200
    assert read_all.json()["data"]["unread_count"] == 0

    count = await client.get("/api/v1/me/notifications/unread-count", headers=auth(owner))
    assert count.json()["data"]["count"] == 0


async def test_rejected_business_visible_to_owner_only(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    other = await create_user("09150000005", UserRole.CUSTOMER)
    admin = await create_user("09150000006", UserRole.ADMIN, permissions=["business.approve"])
    await _reject(client, business, admin, "اطلاعات ناقص")

    anonymous = await client.get(f"/api/v1/businesses/{business.slug}")
    assert anonymous.status_code == 404

    stranger = await client.get(f"/api/v1/businesses/{business.slug}", headers=auth(other))
    assert stranger.status_code == 404

    owner_view = await client.get(f"/api/v1/businesses/{business.slug}", headers=auth(owner))
    assert owner_view.status_code == 200
    data = owner_view.json()["data"]
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "اطلاعات ناقص"
    assert data["is_owner"] is True

    admin_view = await client.get(f"/api/v1/businesses/{business.slug}", headers=auth(admin))
    assert admin_view.status_code == 200
    assert admin_view.json()["data"]["is_owner"] is False


async def test_owner_edit_resubmits_rejected_business(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    admin = await create_user("09150000007", UserRole.ADMIN, permissions=["business.approve"])
    await _reject(client, business, admin, "آدرس اشتباه")

    edited = await client.patch(
        f"/api/v1/businesses/{business.id}",
        json={"short_description": "توضیح کوتاه اصلاح‌شده"},
        headers=auth(owner),
    )
    assert edited.status_code == 200
    assert edited.json()["data"]["status"] == "pending"
    assert edited.json()["data"]["rejection_reason"] is None

    await db_session.refresh(business)
    assert business.status == BusinessStatus.PENDING
    assert business.rejection_reason is None

    owner_view = await client.get(f"/api/v1/businesses/{business.slug}", headers=auth(owner))
    assert owner_view.status_code == 200
    assert owner_view.json()["data"]["status"] == "pending"

    mine = await client.get("/api/v1/me/businesses", headers=auth(owner))
    item = mine.json()["data"]["items"][0]
    assert item["status"] == "pending"
    assert item["rejection_reason"] is None


async def test_broadcast_targets_audience_and_requires_permission(client, db_session, create_user):
    owner = await create_user("09150000008", UserRole.OWNER)
    customer = await create_user("09150000009", UserRole.CUSTOMER)
    admin = await create_user(
        "09150000010", UserRole.ADMIN, permissions=["notification.manage"]
    )

    denied = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"title": "اطلاعیه", "body": "متن", "audience": "all"},
        headers=auth(customer),
    )
    assert denied.status_code == 403

    response = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={
            "title": "اطلاعیه مالکان",
            "body": "متن اطلاعیه",
            "audience": "owners",
            "action_url": "/me/businesses",
        },
        headers=auth(admin),
    )
    assert response.status_code == 200
    assert response.json()["data"]["sent"] == 1

    notifications = (await db_session.execute(sa.select(Notification))).scalars().all()
    assert len(notifications) == 1
    assert notifications[0].user_id == owner.id
    assert notifications[0].type == "announcement"
    assert notifications[0].payload["action_url"] == "/me/businesses"

    customers = await client.get("/api/v1/me/notifications", headers=auth(customer))
    assert customers.json()["data"]["items"] == []


async def test_broadcast_to_single_receiver(client, db_session, create_user):
    owner = await create_user("09150000011", UserRole.OWNER)
    other = await create_user("09150000012", UserRole.OWNER)
    admin = await create_user(
        "09150000013", UserRole.ADMIN, permissions=["notification.manage"]
    )

    response = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={
            "title": "پیام مستقیم",
            "body": "فقط برای یک کاربر",
            "audience": "user",
            "user_id": str(owner.id),
        },
        headers=auth(admin),
    )
    assert response.status_code == 200
    assert response.json()["data"]["sent"] == 1

    notifications = (await db_session.execute(sa.select(Notification))).scalars().all()
    assert [item.user_id for item in notifications] == [owner.id]

    missing = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"title": "پیام", "body": "متن", "audience": "user"},
        headers=auth(admin),
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "user_id_required"
    assert other.id != owner.id
