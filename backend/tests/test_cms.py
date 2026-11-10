import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business, BusinessStatus
from app.models.category import Category
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _admin(create_user, phone="09160000001"):
    return await create_user(
        phone,
        UserRole.ADMIN,
        permissions=[
            "category.read",
            "category.manage",
            "ad.manage",
            "admin.settings.manage",
        ],
    )


async def test_categories_subcategories_and_tags_crud(client, db_session, create_user):
    await seed_categories(db_session)
    await db_session.commit()
    admin = await _admin(create_user)

    categories = await client.get("/api/v1/admin/categories", headers=auth(admin))
    assert categories.status_code == 200
    assert len(categories.json()["data"]["items"]) >= 18

    created = await client.post(
        "/api/v1/admin/categories",
        json={"name": "دسته تست", "slug": "test-category", "icon": "🧪", "sort_order": 99},
        headers=auth(admin),
    )
    assert created.status_code == 200
    category_id = created.json()["data"]["id"]
    assert created.json()["data"]["slug"] == "test-category"

    updated = await client.patch(
        f"/api/v1/admin/categories/{category_id}",
        json={"name": "دسته ویرایش‌شده", "slug": "test-category-edited", "is_active": False},
        headers=auth(admin),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "دسته ویرایش‌شده"
    assert updated.json()["data"]["slug"] == "test-category-edited"

    duplicate_category = await client.post(
        "/api/v1/admin/categories",
        json={"name": "تکراری", "slug": "test-category-edited"},
        headers=auth(admin),
    )
    assert duplicate_category.status_code == 409

    invalid_category = await client.post(
        "/api/v1/admin/categories",
        json={"name": "نامعتبر", "slug": "Not A Slug"},
        headers=auth(admin),
    )
    assert invalid_category.status_code == 422

    sub = await client.post(
        "/api/v1/admin/subcategories",
        json={"category_id": category_id, "name": "زیردسته تست", "slug": "test-sub"},
        headers=auth(admin),
    )
    assert sub.status_code == 200
    sub_id = sub.json()["data"]["id"]
    assert sub.json()["data"]["slug"] == "test-sub"
    renamed = await client.patch(
        f"/api/v1/admin/subcategories/{sub_id}",
        json={"name": "زیردسته ویرایش‌شده", "slug": "test-sub-edited"},
        headers=auth(admin),
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["slug"] == "test-sub-edited"

    duplicate_sub = await client.post(
        "/api/v1/admin/subcategories",
        json={"category_id": category_id, "name": "تکراری", "slug": "test-sub-edited"},
        headers=auth(admin),
    )
    assert duplicate_sub.status_code == 409

    tag = await client.post(
        "/api/v1/admin/tags",
        json={"name": "برچسب تست", "status": "approved"},
        headers=auth(admin),
    )
    assert tag.status_code == 200
    tag_id = tag.json()["data"]["id"]
    tags = await client.get("/api/v1/admin/tags", headers=auth(admin))
    assert tags.status_code == 200
    assert any(item["name"] == "برچسب تست" for item in tags.json()["data"]["items"])
    tag_update = await client.patch(
        f"/api/v1/admin/tags/{tag_id}", json={"name": "برچسب جدید"}, headers=auth(admin)
    )
    assert tag_update.status_code == 200

    deleted_sub = await client.delete(f"/api/v1/admin/subcategories/{sub_id}", headers=auth(admin))
    assert deleted_sub.status_code == 200
    deleted_tag = await client.delete(f"/api/v1/admin/tags/{tag_id}", headers=auth(admin))
    assert deleted_tag.status_code == 200
    deleted_category = await client.delete(
        f"/api/v1/admin/categories/{category_id}", headers=auth(admin)
    )
    assert deleted_category.status_code == 200


async def test_ads_and_settings_crud(client, db_session, create_user):
    admin = await _admin(create_user, "09160000002")

    ad = await client.post(
        "/api/v1/admin/ads",
        json={"title": "بنر تست", "body": "متن", "placement": "home_banner"},
        headers=auth(admin),
    )
    assert ad.status_code == 200
    ad_id = ad.json()["data"]["id"]
    listed = await client.get("/api/v1/admin/ads", headers=auth(admin))
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["id"] == ad_id
    updated = await client.patch(
        f"/api/v1/admin/ads/{ad_id}",
        json={"title": "بنر ویرایش‌شده", "is_active": False},
        headers=auth(admin),
    )
    assert updated.status_code == 200

    trending = await client.get("/api/v1/search/trending")
    assert trending.status_code == 200
    assert trending.json()["data"]["items"]

    saved = await client.put(
        "/api/v1/admin/settings/search_trends",
        json={"value": ["کولر", "لوله"]},
        headers=auth(admin),
    )
    assert saved.status_code == 200
    trending = await client.get("/api/v1/search/trending")
    assert trending.json()["data"]["items"] == ["کولر", "لوله"]
    settings = await client.get("/api/v1/admin/settings", headers=auth(admin))
    assert settings.json()["data"]["search_trends"] == ["کولر", "لوله"]

    deleted = await client.delete(f"/api/v1/admin/ads/{ad_id}", headers=auth(admin))
    assert deleted.status_code == 200


async def test_most_visited_sort_and_view_counter(client, db_session, create_user):
    await seed_categories(db_session)
    await db_session.commit()
    category = (await db_session.execute(sa.select(Category))).scalars().first()
    owner = await create_user("09160000003", UserRole.OWNER)
    low = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="کم‌بازدید",
        slug="low-visit",
        address="بهبهان",
        status=BusinessStatus.APPROVED,
        view_count=1,
    )
    high = Business(
        owner_id=owner.id,
        category_id=category.id,
        name="پربازدید",
        slug="high-visit",
        address="بهبهان",
        status=BusinessStatus.APPROVED,
        view_count=10,
    )
    db_session.add_all([low, high])
    await db_session.commit()

    listed = await client.get("/api/v1/businesses?sort=visited")
    assert listed.status_code == 200
    assert [item["slug"] for item in listed.json()["data"]["items"]][:2] == ["high-visit", "low-visit"]

    await client.get("/api/v1/businesses/low-visit")
    await db_session.refresh(low)
    assert low.view_count == 2


async def test_generic_admin_data_crud_is_superadmin_only(client, create_user):
    superadmin = await create_user("09160000004", UserRole.SUPERADMIN)
    headers = auth(superadmin)

    models = await client.get("/api/v1/admin/data/models", headers=headers)
    assert models.status_code == 200
    names = [item["name"] for item in models.json()["data"]["items"]]
    assert "contact_messages" in names and "reviews" in names

    created = await client.post(
        "/api/v1/admin/data/contact_messages",
        json={"name": "کاربر", "phone": "09120000000", "subject": "پرسش", "body": "متن"},
        headers=headers,
    )
    assert created.status_code == 200
    row_id = created.json()["data"]["id"]

    listed = await client.get(
        "/api/v1/admin/data/contact_messages?q=پرسش", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    updated = await client.patch(
        f"/api/v1/admin/data/contact_messages/{row_id}",
        json={"is_read": True},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["is_read"] is True

    deleted = await client.delete(f"/api/v1/admin/data/contact_messages/{row_id}", headers=headers)
    assert deleted.status_code == 200

    admin = await create_user("09160000005", UserRole.ADMIN, permissions=["category.manage"])
    forbidden = await client.get("/api/v1/admin/data/models", headers=auth(admin))
    assert forbidden.status_code == 403
