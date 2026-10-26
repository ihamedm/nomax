"""Idempotent catalog seed.

The category tree is extracted from the official NOMAX design
(https://ehsan-movahed.github.io/nomax/) and committed as JSON so a fresh
environment can be seeded without network access.
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, Subcategory

SEED_PATH = Path(__file__).parent / "seed_data" / "categories.json"


def load_seed_data() -> list[dict]:
    with SEED_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


async def seed_categories(session: AsyncSession) -> dict[str, int]:
    """Create or update the 18 categories and their subcategories.

    Safe to run repeatedly: existing rows are matched by slug, never duplicated.
    """

    categories_created = 0
    categories_updated = 0
    subcategories_created = 0
    subcategories_updated = 0

    for item in load_seed_data():
        category = (
            await session.execute(select(Category).where(Category.slug == item["slug"]))
        ).scalar_one_or_none()

        if category is None:
            category = Category(
                slug=item["slug"],
                name=item["name"],
                icon=item["icon"],
                sort_order=item["sort_order"],
                is_active=True,
            )
            session.add(category)
            await session.flush()
            categories_created += 1
        else:
            category.name = item["name"]
            category.icon = item["icon"]
            category.sort_order = item["sort_order"]
            category.deleted_at = None
            categories_updated += 1

        existing = {
            sub.slug: sub
            for sub in (
                await session.execute(
                    select(Subcategory).where(Subcategory.category_id == category.id)
                )
            )
            .scalars()
            .all()
        }

        for sub_item in item["subcategories"]:
            subcategory = existing.get(sub_item["slug"])
            if subcategory is None:
                session.add(
                    Subcategory(
                        category_id=category.id,
                        slug=sub_item["slug"],
                        name=sub_item["name"],
                        icon=sub_item["icon"],
                        sort_order=sub_item["sort_order"],
                        standard_tags=sub_item.get("standard_tags", []),
                    )
                )
                subcategories_created += 1
            else:
                subcategory.name = sub_item["name"]
                subcategory.icon = sub_item["icon"]
                subcategory.sort_order = sub_item["sort_order"]
                subcategory.standard_tags = sub_item.get("standard_tags", [])
                subcategory.deleted_at = None
                subcategories_updated += 1

    return {
        "categories_created": categories_created,
        "categories_updated": categories_updated,
        "subcategories_created": subcategories_created,
        "subcategories_updated": subcategories_updated,
    }
