from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.category_suggestion import CategorySuggestionRequest
from app.services import catalog_cache
from app.services.category_suggestions import suggest_category

router = APIRouter(prefix="/categories", tags=["catalog"])


@router.get("")
async def list_categories(
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    catalog = await catalog_cache.ensure_catalog(session, redis)
    return {"data": {"items": catalog["categories"]}}


@router.post("/suggest")


@router.post("/suggest")
async def suggest_business_category(
    payload: CategorySuggestionRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Suggest a category/subcategory for the business wizard.

    Suggestions are advisory. A disabled or unavailable model returns an empty
    result rather than failing the form, so the owner can always pick manually.
    """
    del user
    result = await suggest_category(session, payload.title, payload.description)
    return {"data": result}


@router.get("/subcategories")
async def list_all_subcategories(
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    """Compact catalog used by the picker's inline search.

    The catalog is intentionally small and static enough to load once, so the
    picker can filter both levels locally without a request per keystroke.
    """
    catalog = await catalog_cache.ensure_catalog(session, redis)
    return {"data": {"items": catalog["subcategories"]}}


@router.get("/{category_id}/subcategories")
async def list_subcategories(
    category_id: int,
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    catalog = await catalog_cache.ensure_catalog(session, redis)
    category = next(
        (item for item in catalog["categories"] if item["id"] == category_id), None
    )
    if category is None:
        raise AppError("not_found", "category_not_found", 404)

    items = [item for item in catalog["subcategories"] if item["category_id"] == category_id]
    return {
        "data": {
            "category": {
                "id": category["id"],
                "slug": category["slug"],
                "name": category["name"],
            },
            "items": [
                {
                    "id": item["id"],
                    "category_id": item["category_id"],
                    "slug": item["slug"],
                    "name": item["name"],
                    "icon": item["icon"],
                    "sort_order": item["sort_order"],
                    "standard_tags": item["standard_tags"],
                }
                for item in items
            ],
        }
    }
