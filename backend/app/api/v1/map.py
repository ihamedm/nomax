"""Public map feed: pre-clustered business markers by zoom level."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import get_db
from app.services.map_cache import get_map_view

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/businesses")
async def map_businesses(
    zoom: int = Query(13, ge=3, le=18),
    q: str | None = Query(None, max_length=120),
    cat: str | None = Query(None, max_length=80),
    subcat: str | None = Query(None, max_length=80),
    west: float | None = Query(None, ge=-180, le=180),
    south: float | None = Query(None, ge=-90, le=90),
    east: float | None = Query(None, ge=-180, le=180),
    north: float | None = Query(None, ge=-90, le=90),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    values = (west, south, east, north)
    bbox = None
    if any(value is not None for value in values):
        if any(value is None for value in values):
            raise AppError(
                "validation_error",
                "incomplete_bbox",
                422,
                {"west": west, "south": south, "east": east, "north": north},
            )
        if west >= east or south >= north:
            raise AppError(
                "validation_error",
                "invalid_bbox",
                422,
                {"west": west, "south": south, "east": east, "north": north},
            )
        bbox = (west, south, east, north)

    return await get_map_view(
        session,
        redis,
        zoom=zoom,
        bbox=bbox,
        category_slug=cat,
        subcategory_slug=subcat,
        q=q,
    )
