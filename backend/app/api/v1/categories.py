from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_db
from app.models.category import Category, Subcategory

router = APIRouter(prefix="/categories", tags=["catalog"])


def _category_item(category: Category, subcategory_count: int) -> dict:
    return {
        "id": category.id,
        "slug": category.slug,
        "name": category.name,
        "icon": category.icon,
        "sort_order": category.sort_order,
        "subcategory_count": subcategory_count,
    }


@router.get("")
async def list_categories(session: AsyncSession = Depends(get_db)) -> dict:
    statement = (
        select(Category, func.count(Subcategory.id))
        .outerjoin(
            Subcategory,
            (Subcategory.category_id == Category.id) & (Subcategory.deleted_at.is_(None)),
        )
        .where(Category.deleted_at.is_(None), Category.is_active.is_(True))
        .group_by(Category.id)
        .order_by(Category.sort_order, Category.id)
    )
    rows = (await session.execute(statement)).all()
    return {"data": {"items": [_category_item(category, count) for category, count in rows]}}


@router.get("/{category_id}/subcategories")
async def list_subcategories(category_id: int, session: AsyncSession = Depends(get_db)) -> dict:
    category = await session.get(Category, category_id)
    if category is None or category.deleted_at is not None or not category.is_active:
        raise AppError("not_found", "category_not_found", 404)

    rows = (
        (
            await session.execute(
                select(Subcategory)
                .where(
                    Subcategory.category_id == category_id,
                    Subcategory.deleted_at.is_(None),
                )
                .order_by(Subcategory.sort_order, Subcategory.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "data": {
            "category": {"id": category.id, "slug": category.slug, "name": category.name},
            "items": [
                {
                    "id": subcategory.id,
                    "category_id": subcategory.category_id,
                    "slug": subcategory.slug,
                    "name": subcategory.name,
                    "icon": subcategory.icon,
                    "sort_order": subcategory.sort_order,
                    "standard_tags": list(subcategory.standard_tags or []),
                }
                for subcategory in rows
            ],
        }
    }
