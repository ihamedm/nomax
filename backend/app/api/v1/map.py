"""Public map feed: one cached snapshot of business points.

The browser clusters this snapshot locally, so panning and zooming never issue
another request. The response carries a weak ETag derived from the snapshot
version, letting browsers revalidate with a cheap 304.
"""

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.session import get_db
from app.services.map_cache import get_map_view

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/businesses", response_model=None)
async def map_businesses(
    request: Request,
    response: Response,
    q: str | None = Query(None, max_length=120),
    cat: str | None = Query(None, max_length=80),
    subcat: str | None = Query(None, max_length=80),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict | Response:
    payload = await get_map_view(
        session,
        redis,
        category_slug=cat,
        subcategory_slug=subcat,
        q=q,
    )
    generated_at = payload["data"].get("generated_at") or "0"
    etag = f'W/"{generated_at}"'
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return payload
