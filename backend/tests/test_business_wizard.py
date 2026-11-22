"""Wizard payload coverage: tags, picture, geo validation and geocoding proxy."""

import pytest
import sqlalchemy as sa

from app.api.v1 import geo
from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business
from app.models.category import Category, Subcategory
from app.models.tag import BusinessTag, Tag
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _catalog(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    category = (await db_session.execute(sa.select(Category))).scalars().first()
    subcategory = (
        await db_session.execute(
            sa.select(Subcategory).where(Subcategory.category_id == category.id)
        )
    ).scalars().first()
    return category, subcategory


async def _subcategories(db_session, category, count: int):
    return (
        await db_session.execute(
            sa.select(Subcategory)
            .where(Subcategory.category_id == category.id)
            .order_by(Subcategory.id)
            .limit(count)
        )
    ).scalars().all()


async def test_create_business_accepts_wizard_fields(client, db_session, create_user):
    owner = await create_user("09160000001", UserRole.OWNER)
    category, subcategory = await _catalog(db_session)
    standard_tag = subcategory.standard_tags[0]

    response = await client.post(
        "/api/v1/businesses",
        json={
            "name": "کافه تست",
            "description": "توضیحات کامل",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "short_description": "معرفی کوتاه",
            "phone_business": "09161234567",
            "address": "بهبهان، خیابان امام",
            "geo_lat": 30.5959,
            "geo_lng": 50.2417,
            "instagram": "https://instagram.com/test",
            "is_24h": True,
            "profile_image_url": "https://cdn.example.com/photo.jpg",
            "avatar_url": "https://cdn.example.com/avatar.jpg",
            "tags": [standard_tag, "کافه", "کافه"],
        },
        headers=auth(owner),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["profile_image_url"] == "https://cdn.example.com/photo.jpg"
    assert data["avatar_url"] == "https://cdn.example.com/avatar.jpg"
    assert data["is_license_verified"] is False
    assert data["is_24h"] is True
    assert data["geo"] == {"lat": 30.5959, "lng": 50.2417}

    business = (
        await db_session.execute(sa.select(Business).where(Business.slug == data["slug"]))
    ).scalars().one()
    rows = (
        await db_session.execute(
            sa.select(Tag.name, Tag.is_custom, Tag.status)
            .join(BusinessTag, BusinessTag.tag_id == Tag.id)
            .where(BusinessTag.business_id == business.id)
        )
    ).all()
    tags = {row.name: row for row in rows}
    hidden = set(subcategory.standard_tags[6:])
    assert set(tags) == {standard_tag, "کافه"} | hidden
    assert tags[standard_tag].is_custom is False
    assert tags[standard_tag].status == "approved"
    assert tags["کافه"].is_custom is True
    assert tags["کافه"].status == "pending"


async def test_create_business_rejects_mismatched_subcategory(client, db_session, create_user):
    owner = await create_user("09160000002", UserRole.OWNER)
    await seed_categories(db_session)
    await db_session.commit()
    categories = (await db_session.execute(sa.select(Category))).scalars().all()
    first, second = categories[0], categories[1]
    subcategory = (
        await db_session.execute(
            sa.select(Subcategory).where(Subcategory.category_id == second.id)
        )
    ).scalars().first()

    response = await client.post(
        "/api/v1/businesses",
        json={
            "name": "مغازه",
            "category_id": first.id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان",
        },
        headers=auth(owner),
    )
    assert response.status_code == 422


async def test_create_business_validates_coordinates_and_phone(client, db_session, create_user):
    owner = await create_user("09160000003", UserRole.OWNER)
    category, _ = await _catalog(db_session)

    missing_pair = await client.post(
        "/api/v1/businesses",
        json={"name": "مغازه", "category_id": category.id, "geo_lat": 30.5},
        headers=auth(owner),
    )
    assert missing_pair.status_code == 422

    bad_phone = await client.post(
        "/api/v1/businesses",
        json={"name": "مغازه", "category_id": category.id, "phone_business": "123"},
        headers=auth(owner),
    )
    assert bad_phone.status_code == 422


async def test_create_business_caps_tag_count(client, db_session, create_user):
    owner = await create_user("09160000004", UserRole.OWNER)
    category, _ = await _catalog(db_session)

    response = await client.post(
        "/api/v1/businesses",
        json={
            "name": "مغازه",
            "category_id": category.id,
            "tags": [f"برچسب-{index}" for index in range(31)],
        },
        headers=auth(owner),
    )
    assert response.status_code == 422


async def test_geo_search_proxies_provider(client, monkeypatch):
    calls = {}

    async def fake_fetch(path, params):
        calls["path"] = path
        calls["params"] = params
        return [
            {"display_name": "بهبهان، خوزستان", "lat": "30.59", "lon": "50.24", "type": "city"},
            {"display_name": "نتیجه نامعتبر"},
        ]

    monkeypatch.setattr(geo, "_fetch", fake_fetch)
    response = await client.get("/api/v1/geo/search", params={"q": "بهبهان"})
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert items == [
        {"display_name": "بهبهان، خوزستان", "lat": 30.59, "lng": 50.24, "type": "city"}
    ]
    assert calls["path"] == "/search"
    assert calls["params"]["countrycodes"] == "ir"
    assert calls["params"]["bounded"] == 1
    assert calls["params"]["viewbox"] == geo.settings.GEOCODER_VIEWBOX


async def test_geo_search_rejects_short_query(client):
    response = await client.get("/api/v1/geo/search", params={"q": "به"})
    assert response.status_code == 422


async def test_geo_reverse_returns_address(client, monkeypatch):
    calls = {}

    async def fake_fetch(path, params):
        calls["params"] = params
        return {"display_name": "بهبهان، خیابان امام", "lat": "30.5959", "lon": "50.2417"}

    monkeypatch.setattr(geo, "_fetch", fake_fetch)
    response = await client.get("/api/v1/geo/reverse", params={"lat": 30.5959, "lng": 50.2417})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["display_name"] == "بهبهان، خیابان امام"
    assert data["lat"] == 30.5959
    assert calls["params"]["addressdetails"] == 1


async def test_geo_reverse_drops_country_state_and_city(client, monkeypatch):
    async def fake_fetch(path, params):
        return {
            "display_name": (
                "حسینیه مهاجرین بهبهان, خیابان عدالت, دهستان حومه, بخش مرکزی, "
                "شهرستان بهبهان, استان خوزستان, 63617-80010, ایران"
            ),
            "lat": "30.5959",
            "lon": "50.2417",
            "address": {
                "amenity": "حسینیه مهاجرین بهبهان",
                "road": "خیابان عدالت",
                "city": "دهستان حومه",
                "district": "بخش مرکزی",
                "county": "شهرستان بهبهان",
                "state": "استان خوزستان",
                "postcode": "63617-80010",
                "country": "ایران",
            },
        }

    monkeypatch.setattr(geo, "_fetch", fake_fetch)
    response = await client.get("/api/v1/geo/reverse", params={"lat": 30.5959, "lng": 50.2417})

    assert response.status_code == 200
    assert response.json()["data"]["display_name"] == "حسینیه مهاجرین بهبهان، خیابان عدالت"


async def test_geo_reverse_not_found(client, monkeypatch):
    async def fake_fetch(path, params):
        return {"error": "Unable to geocode"}

    monkeypatch.setattr(geo, "_fetch", fake_fetch)
    response = await client.get("/api/v1/geo/reverse", params={"lat": 0, "lng": 0})
    assert response.status_code == 404


async def test_geo_search_falls_back_to_city_when_street_is_unknown(client, monkeypatch):
    calls: list[str] = []

    async def fake_fetch(path, params):
        calls.append(params["q"])
        if len(calls) == 1:
            return []
        return [
            {"display_name": "بهبهان، خوزستان", "lat": "30.59", "lon": "50.24", "type": "city"}
        ]

    monkeypatch.setattr(geo, "_fetch", fake_fetch)
    response = await client.get(
        "/api/v1/geo/search", params={"q": "بهبهان، خیابان امام خمینی، پلاک ۱۲"}
    )
    assert response.status_code == 200
    assert calls == ["بهبهان، خیابان امام خمینی، پلاک ۱۲", "بهبهان"]
    assert response.json()["data"]["items"][0]["display_name"] == "بهبهان، خوزستان"


async def test_business_limit_is_one_per_owner(client, db_session, create_user):
    owner = await create_user("09160000005", UserRole.OWNER)
    category, _ = await _catalog(db_session)
    body = {"name": "مغازه یک", "category_id": category.id, "address": "بهبهان"}
    first = await client.post("/api/v1/businesses", json=body, headers=auth(owner))
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/businesses",
        json={**body, "name": "مغازه دو"},
        headers=auth(owner),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "business_limit_reached"

    mine = await client.get("/api/v1/me/businesses", headers=auth(owner))
    data = mine.json()["data"]
    assert data["limit"] == 1
    assert data["can_create"] is False
    assert data["max_images"] == 6
    assert len(data["items"]) == 1


async def test_edit_business_accepts_full_wizard_payload(client, db_session, create_user):
    from app.models.business import BusinessStatus

    owner = await create_user("09160000006", UserRole.OWNER)
    category, subcategory = await _catalog(db_session)
    standard_tag = subcategory.standard_tags[0]

    created = await client.post(
        "/api/v1/businesses",
        json={
            "name": "نام اولیه",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان",
        },
        headers=auth(owner),
    )
    assert created.status_code == 200
    business_id = created.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={
            "name": "نام ویرایش‌شده",
            "description": "توضیحات تازه",
            "short_description": "معرفی تازه",
            "phone_business": "06134567890",
            "address": "بهبهان، خیابان عدالت",
            "geo_lat": 30.5959,
            "geo_lng": 50.2417,
            "instagram": "https://instagram.com/edited",
            "is_24h": True,
            "profile_image_url": "https://cdn.example.com/edited.jpg",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "tags": [standard_tag, "برچسب ویرایش"],
        },
        headers=auth(owner),
    )
    assert response.status_code == 200

    detail = await client.get(f"/api/v1/me/businesses/{business_id}", headers=auth(owner))
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["name"] == "نام ویرایش‌شده"
    assert data["description"] == "توضیحات تازه"
    assert data["short_description"] == "معرفی تازه"
    assert data["phone_business"] == "06134567890"
    assert data["address"] == "بهبهان، خیابان عدالت"
    assert data["geo"] == {"lat": 30.5959, "lng": 50.2417}
    assert data["instagram"] == "https://instagram.com/edited"
    assert data["is_24h"] is True
    assert data["profile_image_url"] == "https://cdn.example.com/edited.jpg"
    assert set(data["tags"]) == {standard_tag, "برچسب ویرایش"} | set(
        subcategory.standard_tags[6:]
    )
    assert standard_tag in data["subcategory"]["standard_tags"]

    business = await db_session.get(Business, __import__("uuid").UUID(business_id))
    assert business.status == BusinessStatus.PENDING


async def test_edit_business_any_change_requires_approval(client, db_session, create_user):
    from app.models.business import BusinessStatus

    owner = await create_user("09160000007", UserRole.OWNER)
    category, subcategory = await _catalog(db_session)
    created = await client.post(
        "/api/v1/businesses",
        json={
            "name": "کسب‌وکار ثابت",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان",
        },
        headers=auth(owner),
    )
    business_id = created.json()["data"]["id"]
    business = await db_session.get(Business, __import__("uuid").UUID(business_id))
    business.status = BusinessStatus.APPROVED
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"is_24h": True},
        headers=auth(owner),
    )
    assert response.status_code == 200
    await db_session.refresh(business)
    assert business.status == BusinessStatus.PENDING
    assert business.pending_changes == {"is_24h": {"from": False, "to": True}}


async def test_edit_business_merges_and_drops_reverted_pending_changes(
    client, db_session, create_user
):
    from app.models.business import BusinessStatus

    owner = await create_user("09160000007", UserRole.OWNER)
    category, subcategory = await _catalog(db_session)
    created = await client.post(
        "/api/v1/businesses",
        json={
            "name": "کسب‌وکار ثابت",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان",
            "short_description": "معرفی اول",
        },
        headers=auth(owner),
    )
    business_id = created.json()["data"]["id"]
    business = await db_session.get(Business, __import__("uuid").UUID(business_id))
    business.status = BusinessStatus.APPROVED
    await db_session.commit()

    await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"is_24h": True},
        headers=auth(owner),
    )
    await db_session.refresh(business)
    assert business.pending_changes == {"is_24h": {"from": False, "to": True}}

    await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"short_description": "معرفی دوم"},
        headers=auth(owner),
    )
    await db_session.refresh(business)
    assert business.pending_changes == {
        "is_24h": {"from": False, "to": True},
        "short_description": {"from": "معرفی اول", "to": "معرفی دوم"},
    }

    await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"is_24h": False},
        headers=auth(owner),
    )
    await db_session.refresh(business)
    assert business.pending_changes == {
        "short_description": {"from": "معرفی اول", "to": "معرفی دوم"},
    }


async def test_edit_business_unchanged_payload_keeps_status(client, db_session, create_user):
    from app.models.business import BusinessStatus

    owner = await create_user("09160000007", UserRole.OWNER)
    category, subcategory = await _catalog(db_session)
    created = await client.post(
        "/api/v1/businesses",
        json={
            "name": "کسب‌وکار ثابت",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان",
            "short_description": "معرفی",
            "is_24h": False,
            "tags": [subcategory.standard_tags[0]],
        },
        headers=auth(owner),
    )
    business_id = created.json()["data"]["id"]
    business = await db_session.get(Business, __import__("uuid").UUID(business_id))
    business.status = BusinessStatus.APPROVED
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={
            "name": "کسب‌وکار ثابت",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان",
            "short_description": "معرفی",
            "is_24h": False,
            "tags": [subcategory.standard_tags[0]],
        },
        headers=auth(owner),
    )
    assert response.status_code == 200
    await db_session.refresh(business)
    assert business.status == BusinessStatus.APPROVED


async def test_edit_business_rejects_mismatched_subcategory(client, db_session, create_user):
    owner = await create_user("09160000008", UserRole.OWNER)
    await seed_categories(db_session)
    await db_session.commit()
    categories = (await db_session.execute(sa.select(Category))).scalars().all()
    first, second = categories[0], categories[1]
    foreign_sub = (
        await db_session.execute(
            sa.select(Subcategory).where(Subcategory.category_id == second.id)
        )
    ).scalars().first()
    created = await client.post(
        "/api/v1/businesses",
        json={"name": "مغازه", "category_id": first.id, "address": "بهبهان"},
        headers=auth(owner),
    )
    business_id = created.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"subcategory_id": foreign_sub.id},
        headers=auth(owner),
    )
    assert response.status_code == 422


async def test_business_gallery_create_edit_and_public_detail(client, db_session, create_user):
    from app.models.business import BusinessStatus

    owner = await create_user("09160000009", UserRole.OWNER)
    category, subcategory = await _catalog(db_session)
    photos = [
        {"url": "https://cdn.example.com/one.jpg", "is_main": False},
        {"url": "https://cdn.example.com/two.jpg", "is_main": True},
        {"url": "https://cdn.example.com/three.jpg", "is_main": False},
    ]
    created = await client.post(
        "/api/v1/businesses",
        json={
            "name": "گالری تست",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان",
            "images": photos,
        },
        headers=auth(owner),
    )
    assert created.status_code == 200
    created_data = created.json()["data"]
    assert [image["url"] for image in created_data["images"]] == [
        photo["url"] for photo in photos
    ]
    assert created_data["profile_image_url"] == "https://cdn.example.com/two.jpg"
    assert [image["is_main"] for image in created_data["images"]] == [False, True, False]

    business_id = created_data["id"]
    slug = created_data["slug"]
    business = await db_session.get(Business, __import__("uuid").UUID(business_id))
    business.status = BusinessStatus.APPROVED
    await db_session.commit()

    owner_detail = await client.get(
        f"/api/v1/me/businesses/{business_id}", headers=auth(owner)
    )
    assert owner_detail.status_code == 200
    assert len(owner_detail.json()["data"]["images"]) == 3

    public_detail = await client.get(f"/api/v1/businesses/{slug}")
    assert public_detail.status_code == 200
    assert [image["url"] for image in public_detail.json()["data"]["images"]] == [
        photo["url"] for photo in photos
    ]

    removed = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={
            "images": [
                {"url": "https://cdn.example.com/three.jpg", "is_main": False},
                {"url": "https://cdn.example.com/one.jpg", "is_main": True},
            ]
        },
        headers=auth(owner),
    )
    assert removed.status_code == 200
    updated = removed.json()["data"]
    assert [image["url"] for image in updated["images"]] == [
        "https://cdn.example.com/three.jpg",
        "https://cdn.example.com/one.jpg",
    ]
    assert updated["profile_image_url"] == "https://cdn.example.com/one.jpg"
    assert [image["is_main"] for image in updated["images"]] == [False, True]

    six = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={
            "images": [
                {"url": f"https://cdn.example.com/{index}.jpg", "is_main": index == 0}
                for index in range(6)
            ]
        },
        headers=auth(owner),
    )
    assert six.status_code == 200
    assert len(six.json()["data"]["images"]) == 6

    too_many = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={
            "images": [
                {"url": f"https://cdn.example.com/too-many-{index}.jpg", "is_main": index == 0}
                for index in range(7)
            ]
        },
        headers=auth(owner),
    )
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "too_many_images"


async def test_picker_catalog_lists_every_subcategory(client, db_session):
    await _catalog(db_session)
    response = await client.get("/api/v1/categories/subcategories")
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert items
    assert all(item["category"]["name"] for item in items)
    assert all(item["category_id"] == item["category"]["id"] for item in items)


async def test_create_business_stores_multiple_subcategories(client, db_session, create_user):
    owner = await create_user("09160000010", UserRole.OWNER)
    category, _ = await _catalog(db_session)
    first, second = await _subcategories(db_session, category, 2)

    response = await client.post(
        "/api/v1/businesses",
        json={
            "name": "چند مهارتی",
            "category_id": category.id,
            "subcategory_ids": [first.id, second.id],
            "address": "بهبهان",
        },
        headers=auth(owner),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert {item["id"] for item in data["subcategories"]} == {first.id, second.id}
    assert data["subcategory"]["id"] == first.id

    detail = await client.get(f"/api/v1/me/businesses/{data['id']}", headers=auth(owner))
    assert {item["id"] for item in detail.json()["data"]["subcategories"]} == {
        first.id,
        second.id,
    }


async def test_multiple_subcategories_must_share_the_business_category(
    client, db_session, create_user
):
    owner = await create_user("09160000011", UserRole.OWNER)
    await seed_categories(db_session)
    await db_session.commit()
    first, second = (
        await db_session.execute(sa.select(Category).order_by(Category.id).limit(2))
    ).scalars().all()
    own_sub = (await _subcategories(db_session, first, 1))[0]
    foreign_sub = (await _subcategories(db_session, second, 1))[0]

    response = await client.post(
        "/api/v1/businesses",
        json={
            "name": "مخلوط",
            "category_id": first.id,
            "subcategory_ids": [own_sub.id, foreign_sub.id],
            "address": "بهبهان",
        },
        headers=auth(owner),
    )
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "subcategory_category_mismatch"


async def test_edit_business_replaces_subcategory_set(client, db_session, create_user):
    owner = await create_user("09160000012", UserRole.OWNER)
    category, _ = await _catalog(db_session)
    first, second, third = await _subcategories(db_session, category, 3)

    created = await client.post(
        "/api/v1/businesses",
        json={
            "name": "مغازه",
            "category_id": category.id,
            "subcategory_ids": [first.id, second.id],
            "address": "بهبهان",
        },
        headers=auth(owner),
    )
    business_id = created.json()["data"]["id"]

    replaced = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"subcategory_ids": [third.id]},
        headers=auth(owner),
    )
    assert replaced.status_code == 200
    data = replaced.json()["data"]
    assert [item["id"] for item in data["subcategories"]] == [third.id]
    assert data["subcategory"]["id"] == third.id

    # A payload without subcategory keys keeps the current selection.
    untouched = await client.patch(
        f"/api/v1/businesses/{business_id}",
        json={"short_description": "معرفی"},
        headers=auth(owner),
    )
    assert [item["id"] for item in untouched.json()["data"]["subcategories"]] == [third.id]


async def test_business_slug_is_transliterated_and_deduplicated(client, db_session, create_user):
    first_owner = await create_user("09160000031", UserRole.OWNER)
    second_owner = await create_user("09160000032", UserRole.OWNER)
    category, _ = await _catalog(db_session)
    body = {"name": "کافه ستاره", "category_id": category.id, "address": "بهبهان"}

    first = await client.post("/api/v1/businesses", json=body, headers=auth(first_owner))
    second = await client.post("/api/v1/businesses", json=body, headers=auth(second_owner))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["slug"] == "kafe-stare"
    assert second.json()["data"]["slug"] == "kafe-stare-2"

    detail = await client.get("/api/v1/businesses/kafe-stare-2", headers=auth(second_owner))
    assert detail.status_code == 200
    assert detail.json()["data"]["slug"] == "kafe-stare-2"
