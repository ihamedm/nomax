"""Subcategory tag management: bulk input, visibility subset and auto-attach."""

import sqlalchemy as sa

from app.core.security import create_access_token
from app.db.seed import seed_categories
from app.models.business import Business
from app.models.category import Subcategory
from app.models.tag import BusinessTag, Tag
from app.models.user import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def _admin(create_user, phone="09160000021"):
    return await create_user(
        phone,
        UserRole.ADMIN,
        permissions=["category.read", "category.manage", "business.create"],
    )


async def _subcategory_with_many_tags(db_session):
    await seed_categories(db_session)
    await db_session.commit()
    rows = (await db_session.execute(sa.select(Subcategory))).scalars().all()
    subcategory = next(
        (row for row in rows if len(row.standard_tags or []) > 6), None
    )
    assert subcategory is not None
    return subcategory


async def test_admin_tag_list_is_paginated_and_filtered(client, db_session, create_user):
    admin = await _admin(create_user)
    for index in range(25):
        db_session.add(Tag(name=f"pagination-tag-{index:02d}", status="approved"))
    await db_session.commit()

    first = await client.get(
        "/api/v1/admin/tags?q=pagination-tag&per_page=10&page=1", headers=auth(admin)
    )
    assert first.status_code == 200
    assert len(first.json()["data"]["items"]) == 10
    assert first.json()["meta"]["total"] == 25
    assert first.json()["meta"]["pages"] == 3

    third = await client.get(
        "/api/v1/admin/tags?q=pagination-tag&per_page=10&page=3", headers=auth(admin)
    )
    assert len(third.json()["data"]["items"]) == 5

    pending = await client.get(
        "/api/v1/admin/tags?q=pagination-tag&status=pending", headers=auth(admin)
    )
    assert pending.json()["meta"]["total"] == 0


async def test_subcategory_visible_tags_are_limited_and_pruned(client, db_session, create_user):
    admin = await _admin(create_user)
    subcategory = await _subcategory_with_many_tags(db_session)

    visible = list(subcategory.standard_tags[:3])
    updated = await client.patch(
        f"/api/v1/admin/subcategories/{subcategory.id}",
        json={"visible_tags": visible},
        headers=auth(admin),
    )
    assert updated.status_code == 200

    listed = await client.get("/api/v1/admin/categories", headers=auth(admin))
    item = next(
        sub
        for category in listed.json()["data"]["items"]
        for sub in category["subcategories"]
        if sub["id"] == subcategory.id
    )
    assert item["visible_tags"] == visible

    too_many = await client.patch(
        f"/api/v1/admin/subcategories/{subcategory.id}",
        json={"visible_tags": subcategory.standard_tags[:7]},
        headers=auth(admin),
    )
    assert too_many.status_code == 422
    assert too_many.json()["error"]["message"] == "too_many_visible_tags"
    assert too_many.json()["error"]["details"]["max"] == 6

    pruned = await client.patch(
        f"/api/v1/admin/subcategories/{subcategory.id}",
        json={"standard_tags": visible[:2]},
        headers=auth(admin),
    )
    assert pruned.status_code == 200
    listed = await client.get("/api/v1/admin/categories", headers=auth(admin))
    item = next(
        sub
        for category in listed.json()["data"]["items"]
        for sub in category["subcategories"]
        if sub["id"] == subcategory.id
    )
    assert item["visible_tags"] == visible[:2]


async def test_bulk_tag_string_and_hidden_tags_attach_to_business(
    client, db_session, create_user
):
    admin = await _admin(create_user)
    subcategory = await _subcategory_with_many_tags(db_session)
    visible = list(subcategory.standard_tags[:2])
    hidden = list(subcategory.standard_tags[2:])

    updated = await client.patch(
        f"/api/v1/admin/subcategories/{subcategory.id}",
        json={"standard_tags": ", ".join(subcategory.standard_tags), "visible_tags": visible},
        headers=auth(admin),
    )
    assert updated.status_code == 200

    owner = await create_user("09160000022", UserRole.OWNER)
    created = await client.post(
        "/api/v1/businesses",
        json={
            "name": "کسب‌وکار برچسب",
            "category_id": subcategory.category_id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان",
            "tags": [visible[0]],
        },
        headers=auth(owner),
    )
    assert created.status_code == 200

    business = (
        await db_session.execute(
            sa.select(Business).where(Business.slug == created.json()["data"]["slug"])
        )
    ).scalars().one()
    attached = set(
        (
            await db_session.execute(
                sa.select(Tag.name)
                .join(BusinessTag, BusinessTag.tag_id == Tag.id)
                .where(BusinessTag.business_id == business.id)
            )
        ).scalars()
    )
    # The visible pick plus every search-only tag from the subcategory.
    assert attached == {visible[0], *hidden}
    assert set(hidden) <= attached


async def test_sync_subcategory_tags_updates_assigned_businesses(
    client, db_session, create_user
):
    admin = await _admin(create_user, phone="09160000023")
    subcategory = await _subcategory_with_many_tags(db_session)
    original = list(subcategory.standard_tags)
    custom = "برچسب سفارشی همگام‌سازی"
    new_tag = "برچسب تازه همگام‌سازی"

    owner = await create_user("09160000024", UserRole.OWNER)
    created = await client.post(
        "/api/v1/businesses",
        json={
            "name": "کسب‌وکار همگام‌سازی",
            "category_id": subcategory.category_id,
            "subcategory_id": subcategory.id,
            "address": "بهبهان",
            "tags": [original[0], custom],
        },
        headers=auth(owner),
    )
    assert created.status_code == 200

    business = (
        await db_session.execute(
            sa.select(Business).where(Business.slug == created.json()["data"]["slug"])
        )
    ).scalars().one()
    attached_before = set(
        (
            await db_session.execute(
                sa.select(Tag.name)
                .join(BusinessTag, BusinessTag.tag_id == Tag.id)
                .where(BusinessTag.business_id == business.id)
            )
        ).scalars()
    )

    patched = await client.patch(
        f"/api/v1/admin/subcategories/{subcategory.id}",
        json={
            "standard_tags": [original[0], original[1], new_tag],
            "visible_tags": [original[0], original[1]],
        },
        headers=auth(admin),
    )
    assert patched.status_code == 200

    synced = await client.post(
        f"/api/v1/admin/subcategories/{subcategory.id}/sync-tags",
        headers=auth(admin),
    )
    assert synced.status_code == 200
    result = synced.json()["data"]
    assert result["businesses"] == 1
    assert result["tags_added"] == 1
    assert result["tags_removed"] == len(attached_before) - 2

    attached = set(
        (
            await db_session.execute(
                sa.select(Tag.name)
                .join(BusinessTag, BusinessTag.tag_id == Tag.id)
                .where(BusinessTag.business_id == business.id)
            )
        ).scalars()
    )
    # Catalog tags follow the subcategory; the owner's custom tag survives and a
    # visible tag they did not pick stays off the business.
    assert attached == {original[0], new_tag, custom}
    assert original[1] not in attached
