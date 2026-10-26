import pytest

from app.db.seed import seed_categories


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_serves_the_catalog(client, db_session):
    first = await seed_categories(db_session)
    await db_session.commit()
    assert first["categories_created"] == 18
    assert first["subcategories_created"] == 188

    second = await seed_categories(db_session)
    await db_session.commit()
    assert second["categories_created"] == 0
    assert second["subcategories_created"] == 0
    assert second["categories_updated"] == 18
    assert second["subcategories_updated"] == 188

    response = await client.get("/api/v1/categories")
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 18

    by_slug = {item["slug"]: item for item in items}
    assert by_slug["automotive"]["name"] == "خودرو و حمل‌ونقل"
    assert by_slug["automotive"]["icon"] == "🚗"
    assert by_slug["automotive"]["subcategory_count"] > 0
    assert [item["sort_order"] for item in items] == sorted(item["sort_order"] for item in items)

    automotive_id = by_slug["automotive"]["id"]
    response = await client.get(f"/api/v1/categories/{automotive_id}/subcategories")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["category"]["slug"] == "automotive"
    mechanic = next(item for item in body["items"] if item["slug"] == "mechanic")
    assert mechanic["name"] == "مکانیک"
    assert "تعمیر موتور" in mechanic["standard_tags"]


@pytest.mark.asyncio
async def test_unknown_category_returns_404(client):
    response = await client.get("/api/v1/categories/999999/subcategories")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
