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
    owner = await create_user("09140000001", UserRole.OWNER)
    business = Business(owner_id=owner.id, category_id=category.id, name="biz",
                        slug="biz-admin", address="بهبهان", status=BusinessStatus.PENDING)
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return owner, business


async def test_admin_approves_business(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    admin = await create_user("09140000002", UserRole.ADMIN, permissions=["business.approve"])
    response = await client.patch(f"/api/v1/admin/businesses/{business.id}/approve", headers=auth(admin))
    assert response.status_code == 200
    await db_session.refresh(business)
    assert business.status == BusinessStatus.APPROVED


async def test_admin_rejects_business_with_reason(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    admin = await create_user("09140000006", UserRole.ADMIN, permissions=["business.approve"])

    rejected = await client.patch(
        f"/api/v1/admin/businesses/{business.id}/reject",
        json={"reason": "مدرک ناقص"},
        headers=auth(admin),
    )
    assert rejected.status_code == 200
    await db_session.refresh(business)
    assert business.status == BusinessStatus.REJECTED
    assert business.rejection_reason == "مدرک ناقص"

    approved = await client.patch(f"/api/v1/admin/businesses/{business.id}/approve", headers=auth(admin))
    assert approved.status_code == 200
    await db_session.refresh(business)
    assert business.status == BusinessStatus.APPROVED
    assert business.rejection_reason is None


async def test_is_verified_requires_admin_verified_license(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)

    missing = await client.patch(
        f"/api/v1/admin/businesses/{business.id}/verify-license",
        headers=auth(await create_user("09140000003", UserRole.ADMIN, permissions=["business.license.verify"])),
    )
    assert missing.status_code == 404

    license_res = await client.post(
        f"/api/v1/businesses/{business.id}/license",
        json={"license_number": "123"},
        headers=auth(owner),
    )
    assert license_res.status_code == 200

    admin = await create_user("09140000004", UserRole.ADMIN, permissions=["business.license.verify"])
    verified = await client.patch(f"/api/v1/admin/businesses/{business.id}/verify-license", headers=auth(admin))
    assert verified.status_code == 200
    await db_session.refresh(business)
    assert business.is_verified is True


async def test_tag_list_accepts_four_and_caps_total(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    ok = await client.post(
        f"/api/v1/businesses/{business.id}/tags",
        json={"tags": ["a", "b", "c", "d"]},
        headers=auth(owner),
    )
    assert ok.status_code == 200
    too_many = await client.post(
        f"/api/v1/businesses/{business.id}/tags",
        json={"tags": [f"tag-{index}" for index in range(31)]},
        headers=auth(owner),
    )
    assert too_many.status_code == 422


async def test_admin_business_cms_crud_and_pagination(client, db_session, create_user):
    owner, existing = await _setup(db_session, create_user)
    cms_owner = await create_user("9140000008", UserRole.OWNER)
    admin = await create_user(
        "09140000007",
        UserRole.ADMIN,
        permissions=["business.read", "business.create", "business.update", "business.delete"],
    )

    created = await client.post(
        "/api/v1/admin/businesses",
        json={
            "name": "کسب‌وکار جدید",
            "category_id": existing.category_id,
            "address": "بهبهان، خیابان اصلی",
            "owner_phone": "09140000008",
        },
        headers=auth(admin),
    )
    assert created.status_code == 200
    created_data = created.json()["data"]
    business_id = created_data["id"]
    assert created_data["status"] == "pending"
    assert created_data["owner"]["phone"] == "9140000008"

    listed = await client.get(
        "/api/v1/admin/businesses?status=pending&page=1&per_page=1", headers=auth(admin)
    )
    assert listed.status_code == 200
    assert listed.json()["meta"] == {"page": 1, "per_page": 1, "total": 2, "pages": 2}

    detail = await client.get(f"/api/v1/admin/businesses/{business_id}", headers=auth(admin))
    assert detail.status_code == 200
    assert detail.json()["data"]["category"]["id"] == existing.category_id

    updated = await client.patch(
        f"/api/v1/admin/businesses/{business_id}",
        json={"name": "نام ویرایش‌شده", "status": "approved"},
        headers=auth(admin),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "نام ویرایش‌شده"
    assert updated.json()["data"]["status"] == "approved"

    deleted = await client.delete(f"/api/v1/admin/businesses/{business_id}", headers=auth(admin))
    assert deleted.status_code == 200
    missing = await client.get(f"/api/v1/admin/businesses/{business_id}", headers=auth(admin))
    assert missing.status_code == 404


async def test_admin_business_list_filters_by_owner_and_returns_thumbnail(
    client, db_session, create_user
):
    owner, business = await _setup(db_session, create_user)
    await create_user("9140000009", UserRole.OWNER)
    business.profile_image_url = "/uploads/businesses/demo/main.webp"
    db_session.add(business)
    await db_session.commit()

    admin = await create_user("0914000010", UserRole.ADMIN, permissions=["business.read"])
    listed = await client.get(
        f"/api/v1/admin/businesses?owner_id={owner.id}", headers=auth(admin)
    )
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["meta"]["total"] == 1
    item = payload["data"]["items"][0]
    assert item["owner"]["id"] == str(owner.id)
    assert item["profile_image_url"] == "/uploads/businesses/demo/main.webp"
    assert item["category"]["icon"]

    invalid = await client.get(
        "/api/v1/admin/businesses?owner_id=not-a-uuid", headers=auth(admin)
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["message"] == "invalid_owner_id"


async def test_business_trash_restore_and_permanent_delete(client, db_session, create_user):
    owner, business = await _setup(db_session, create_user)
    admin = await create_user(
        "0914000011", UserRole.ADMIN, permissions=["business.read", "business.delete"]
    )
    url = f"/api/v1/admin/businesses/{business.id}"

    deleted = await client.delete(url, headers=auth(admin))
    assert deleted.status_code == 200

    trash = await client.get("/api/v1/admin/businesses?trash=true", headers=auth(admin))
    assert [item["id"] for item in trash.json()["data"]["items"]] == [str(business.id)]
    assert trash.json()["data"]["items"][0]["deleted_at"] is not None
    normal = await client.get("/api/v1/admin/businesses", headers=auth(admin))
    assert str(business.id) not in {item["id"] for item in normal.json()["data"]["items"]}

    restored = await client.post(f"{url}/restore", headers=auth(admin))
    assert restored.status_code == 200
    assert restored.json()["data"]["deleted_at"] is None

    # Permanent delete is only allowed from trash.
    forbidden = await client.delete(f"{url}/permanent", headers=auth(admin))
    assert forbidden.status_code == 404

    await client.delete(url, headers=auth(admin))
    purged = await client.delete(f"{url}/permanent", headers=auth(admin))
    assert purged.status_code == 200
    assert purged.json()["data"]["permanent"] is True

    remaining = (
        await db_session.execute(sa.select(Business).where(Business.id == business.id))
    ).scalar_one_or_none()
    assert remaining is None


async def test_admin_business_wizard_owner_images_and_tags(client, db_session, create_user):
    owner, existing = await _setup(db_session, create_user)
    admin = await create_user(
        "0914000013",
        UserRole.ADMIN,
        permissions=["business.read", "business.create", "business.update"],
    )

    searched = await client.get(
        "/api/v1/admin/businesses/owners?q=09140000001", headers=auth(admin)
    )
    assert searched.status_code == 200
    assert [item["id"] for item in searched.json()["data"]["items"]] == [str(owner.id)]

    created_owner = await client.post(
        "/api/v1/admin/businesses/owners",
        json={"phone": "09140000140", "full_name": "مالک جدید"},
        headers=auth(admin),
    )
    assert created_owner.status_code == 200
    new_owner = created_owner.json()["data"]
    assert new_owner["role"] == "owner"

    created = await client.post(
        "/api/v1/admin/businesses",
        json={
            "owner_id": new_owner["id"],
            "name": "ویزارد کامل",
            "category_id": existing.category_id,
            "address": "بهبهان، خیابان اصلی",
            "short_description": "معرفی کوتاه",
            "description": "توضیحات کامل",
            "phone_business": "09140000123",
            "instagram": "https://instagram.com/demo",
            "geo_lat": 30.59,
            "geo_lng": 50.24,
            "is_24h": True,
            "is_verified": True,
            "status": "approved",
            "profile_image_url": "/uploads/businesses/demo/main.webp",
            "images": [
                {"url": "/uploads/businesses/demo/main.webp", "is_main": True, "sort_order": 0},
                {"url": "/uploads/businesses/demo/second.webp", "is_main": False, "sort_order": 1},
            ],
            "tags": ["تعمیرکار", "۲۴ ساعته"],
        },
        headers=auth(admin),
    )
    assert created.status_code == 200
    data = created.json()["data"]
    business_id = data["id"]
    assert data["owner"]["id"] == new_owner["id"]
    assert data["is_verified"] is True
    assert data["status"] == "approved"
    assert data["geo"] == {"lat": 30.59, "lng": 50.24}
    assert data["profile_image_url"] == "/uploads/businesses/demo/main.webp"
    assert [image["url"] for image in data["images"]] == [
        "/uploads/businesses/demo/main.webp",
        "/uploads/businesses/demo/second.webp",
    ]
    assert data["tags"] == ["تعمیرکار", "۲۴ ساعته"]

    detail = await client.get(f"/api/v1/admin/businesses/{business_id}", headers=auth(admin))
    assert detail.status_code == 200
    assert len(detail.json()["data"]["images"]) == 2

    updated = await client.patch(
        f"/api/v1/admin/businesses/{business_id}",
        json={
            "owner_id": str(owner.id),
            "images": [{"url": "/uploads/businesses/demo/new.webp", "is_main": True}],
            "tags": ["برچسب تازه"],
            "rejection_reason": None,
        },
        headers=auth(admin),
    )
    assert updated.status_code == 200
    updated_data = updated.json()["data"]
    assert updated_data["owner"]["id"] == str(owner.id)
    assert [image["url"] for image in updated_data["images"]] == [
        "/uploads/businesses/demo/new.webp"
    ]
    assert updated_data["tags"] == ["برچسب تازه"]


async def test_admin_attention_counts_pending_reviews_and_businesses(
    client, db_session, create_user
):
    from app.models.review import Review

    owner, business = await _setup(db_session, create_user)
    customer = await create_user("09140000150", UserRole.CUSTOMER)
    db_session.add(
        Review(business_id=business.id, user_id=customer.id, rating=5, status="pending")
    )
    await db_session.commit()

    admin = await create_user(
        "09140000151", UserRole.ADMIN, permissions=["business.read", "review.read"]
    )
    both = await client.get("/api/v1/admin/attention", headers=auth(admin))
    assert both.status_code == 200
    assert both.json()["data"] == {"businesses": 1, "reviews": 1, "total": 2}

    business_only = await create_user(
        "09140000152", UserRole.ADMIN, permissions=["business.read"]
    )
    partial = await client.get("/api/v1/admin/attention", headers=auth(business_only))
    assert partial.status_code == 200
    assert partial.json()["data"] == {"businesses": 1, "reviews": 0, "total": 1}


async def test_permanent_business_delete_blocked_by_relations(client, db_session, create_user):
    from app.models.license import License

    owner, business = await _setup(db_session, create_user)
    db_session.add(License(business_id=business.id, license_number="12345"))
    await db_session.commit()
    admin = await create_user("0914000012", UserRole.ADMIN, permissions=["business.delete"])
    url = f"/api/v1/admin/businesses/{business.id}"

    await client.delete(url, headers=auth(admin))
    blocked = await client.delete(f"{url}/permanent", headers=auth(admin))
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "business_has_relations"
    assert blocked.json()["error"]["details"]["related"] == [{"type": "licenses", "count": 1}]

    await db_session.execute(sa.delete(License).where(License.business_id == business.id))
    await db_session.commit()
    purged = await client.delete(f"{url}/permanent", headers=auth(admin))
    assert purged.status_code == 200
