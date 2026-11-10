"""Smoke coverage for the remaining §4 endpoints not exercised elsewhere."""

import io

import sqlalchemy as sa
from PIL import Image

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.notification import Notification
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _category(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    return (await db_session.execute(sa.select(Category))).scalars().first()


def _image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (20, 120, 200)).save(buffer, format="JPEG")
    return buffer.getvalue()


async def test_business_crud_qr_and_upload(client, db_session, create_user):
    owner = await create_user("09150000001", UserRole.OWNER)
    category = await _category(db_session)

    created = await client.post(
        "/api/v1/businesses",
        json={"name": "کارگاه تست", "category_id": category.id, "address": "بهبهان"},
        headers=auth(owner),
    )
    assert created.status_code == 200
    business_id = created.json()["data"]["id"]
    slug = created.json()["data"]["slug"]

    updated = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"short_description": "توضیح تازه"},
        headers=auth(owner),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["short_description"] == "توضیح تازه"

    qr = await client.get(f"/api/v1/businesses/{business_id}/qr")
    assert qr.status_code == 200
    assert qr.headers["content-type"].startswith("image/svg+xml")

    upload = await client.post(
        "/api/v1/uploads/image",
        files={"file": ("photo.jpg", _image_bytes(), "image/jpeg")},
        headers=auth(owner),
    )
    assert upload.status_code == 200
    assert upload.json()["data"]["url"].startswith("/uploads/")

    deleted = await client.delete(f"/api/v1/businesses/{business_id}", headers=auth(owner))
    assert deleted.status_code == 200
    assert (await client.get(f"/api/v1/businesses/{slug}")).status_code == 404


async def test_quote_cancel_owner_businesses_and_analytics(client, db_session, create_user):
    customer = await create_user("09150000002")
    owner = await create_user("09150000003", UserRole.OWNER)
    category = await _category(db_session)
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="فروشگاه",
        slug="shop-analytics",
        address="بهبهان",
        status=BusinessStatus.APPROVED,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)

    quote = await client.post(
        "/api/v1/quotes/requests",
        json={"title": "خرید", "category_id": category.id, "address": "بهبهان"},
        headers=auth(customer),
    )
    quote_id = quote.json()["data"]["id"]
    cancelled = await client.post(f"/api/v1/quotes/requests/{quote_id}/cancel", headers=auth(customer))
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"

    mine = await client.get("/api/v1/me/businesses", headers=auth(owner))
    assert mine.status_code == 200
    assert [item["id"] for item in mine.json()["data"]["items"]] == [str(business.id)]

    analytics = await client.get(
        f"/api/v1/me/businesses/{business.id}/analytics", headers=auth(owner)
    )
    assert analytics.status_code == 200
    assert analytics.json()["data"]["business_id"] == str(business.id)


async def test_notifications_and_devices(client, db_session, create_user):
    user = await create_user("09150000004")
    notification = Notification(user_id=user.id, title="سلام", body="متن اعلان")
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)

    listed = await client.get("/api/v1/notifications", headers=auth(user))
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["is_read"] is False
    alias = await client.get("/api/v1/me/notifications", headers=auth(user))
    assert alias.status_code == 200
    assert alias.json()["data"]["items"][0]["id"] == str(notification.id)

    read = await client.patch(f"/api/v1/notifications/{notification.id}/read", headers=auth(user))
    assert read.status_code == 200
    assert read.json()["data"]["is_read"] is True

    device = await client.post(
        "/api/v1/devices",
        json={"provider": "web", "token": "device-token"},
        headers=auth(user),
    )
    assert device.status_code == 200
    removed = await client.delete(
        f"/api/v1/devices/{device.json()['data']['id']}", headers=auth(user)
    )
    assert removed.status_code == 200
    assert removed.json()["data"]["is_active"] is False


async def test_admin_remaining_endpoints(client, db_session, create_user):
    owner = await create_user("09150000005", UserRole.OWNER)
    customer = await create_user("09150000006")
    category = await _category(db_session)
    business = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="ادمین تست",
        slug="admin-extra",
        address="بهبهان",
        status=BusinessStatus.PENDING,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)

    admin = await create_user(
        "09150000007",
        UserRole.ADMIN,
        permissions=[
            "business.approve",
            "business.read",
            "review.read",
            "stats.read",
            "category.suggestion.manage",
            "ad.manage",
            "admin.settings.manage",
        ],
    )

    listed = await client.get("/api/v1/admin/businesses?status=pending", headers=auth(admin))
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["slug"] == "admin-extra"

    toggled = await client.patch(
        f"/api/v1/admin/businesses/{business.id}/toggle-24h", headers=auth(admin)
    )
    assert toggled.status_code == 200
    assert toggled.json()["data"]["is_24h"] is True

    reviews = await client.get("/api/v1/admin/reviews?status=pending", headers=auth(admin))
    assert reviews.status_code == 200

    stats = await client.get("/api/v1/admin/stats/overview", headers=auth(admin))
    assert stats.status_code == 200
    assert stats.json()["data"]["pending"] >= 1

    suggested = await client.post(
        "/api/v1/suggestions/categories",
        json={
            "name": "تعمیر کولر",
            "description": "زیردسته جدید",
            "type": "new_subcategory",
            "parent_id": category.id,
        },
        headers=auth(customer),
    )
    assert suggested.status_code == 200
    suggestion_id = suggested.json()["data"]["id"]
    suggestions = await client.get(
        "/api/v1/admin/category-suggestions?status=pending", headers=auth(admin)
    )
    assert suggestions.status_code == 200
    assert suggestions.json()["data"]["items"][0]["id"] == suggestion_id
    moderated = await client.patch(
        f"/api/v1/admin/category-suggestions/{suggestion_id}",
        json={"status": "approved"},
        headers=auth(admin),
    )
    assert moderated.status_code == 200
    subcategories = await client.get(f"/api/v1/categories/{category.id}/subcategories")
    assert "تعمیر کولر" in [item["name"] for item in subcategories.json()["data"]["items"]]

    ad = await client.post(
        "/api/v1/ads", json={"title": "بنر تست", "placement": "home_banner"}, headers=auth(admin)
    )
    assert ad.status_code == 200
    public_ads = await client.get("/api/v1/ads")
    assert public_ads.status_code == 200
    assert public_ads.json()["data"]["items"][0]["title"] == "بنر تست"

    contact = await client.post(
        "/api/v1/contact",
        json={"name": "کاربر", "phone": "09120000000", "subject": "پرسش", "body": "متن"},
    )
    assert contact.status_code == 200
    messages = await client.get("/api/v1/admin/contact-messages", headers=auth(admin))
    assert messages.status_code == 200
    assert len(messages.json()["data"]["items"]) == 1
