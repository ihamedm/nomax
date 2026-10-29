"""Address geocoding for the business location picker.

The browser talks to our API instead of a third-party geocoder directly:
that keeps the provider configurable, avoids CORS surprises and lets us set
a descriptive User-Agent (required by the public Nominatim service).
"""

import re

import httpx
from fastapi import APIRouter, Query

from app.core.config import settings
from app.core.errors import AppError

router = APIRouter(prefix="/geo", tags=["geo"])


def _endpoint(path: str) -> str:
    return f"{settings.GEOCODER_URL.rstrip('/')}/{path.lstrip('/')}"


def _candidates(q: str) -> list[str]:
    """Full address first, then the city when the full text has no match.

    Owners often include a plaque number or a street that the geocoder does
    not know; falling back to the first comma-separated part (typically the
    city) still gives them a usable starting point to drag the pin.
    """

    candidates = [q.strip()]
    parts = [part.strip() for part in re.split(r"[،,]", q) if part.strip()]
    if len(parts) >= 2 and parts[0] not in candidates:
        candidates.append(parts[0])
    return [candidate for candidate in candidates if candidate]


async def _fetch(path: str, params: dict) -> dict | list:
    headers = {
        "User-Agent": settings.GEOCODER_USER_AGENT,
        "Accept-Language": "fa,en;q=0.8",
    }
    try:
        async with httpx.AsyncClient(
            timeout=settings.GEOCODER_TIMEOUT_SECONDS, headers=headers
        ) as client:
            response = await client.get(_endpoint(path), params=params)
    except httpx.HTTPError:
        raise AppError("geocoder_unavailable", "geocoder_unavailable", 502)

    if response.status_code != 200:
        raise AppError("geocoder_unavailable", "geocoder_unavailable", 502)

    try:
        return response.json()
    except ValueError:
        raise AppError("geocoder_invalid_response", "geocoder_invalid_response", 502)


def _parse_search(payload: dict | list) -> list[dict]:
    items: list[dict] = []
    if not isinstance(payload, list):
        return items
    for row in payload:
        try:
            items.append(
                {
                    "display_name": row.get("display_name") or "",
                    "lat": float(row["lat"]),
                    "lng": float(row["lon"]),
                    "type": row.get("type"),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return items


@router.get("/search")
async def search_address(
    q: str = Query(..., min_length=3, max_length=200),
    limit: int = Query(5, ge=1, le=10),
) -> dict:
    params = {
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": limit,
        "countrycodes": settings.GEOCODER_COUNTRY_CODES,
        "accept-language": "fa",
    }
    if settings.GEOCODER_VIEWBOX:
        params["viewbox"] = settings.GEOCODER_VIEWBOX
        params["bounded"] = 1 if settings.GEOCODER_BOUNDED else 0

    items: list[dict] = []
    for candidate in _candidates(q):
        payload = await _fetch("/search", {**params, "q": candidate})
        items = _parse_search(payload)
        if items:
            break
    return {"data": {"items": items}}


@router.get("/reverse")
async def reverse_address(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
) -> dict:
    payload = await _fetch(
        "/reverse",
        {
            "lat": lat,
            "lon": lng,
            "format": "jsonv2",
            "zoom": 18,
            "accept-language": "fa",
        },
    )

    if not isinstance(payload, dict) or not payload.get("display_name"):
        raise AppError("geocoder_not_found", "geocoder_not_found", 404)

    try:
        resolved_lat = float(payload["lat"])
        resolved_lng = float(payload["lon"])
    except (KeyError, TypeError, ValueError):
        resolved_lat, resolved_lng = lat, lng

    return {
        "data": {
            "display_name": payload["display_name"],
            "lat": resolved_lat,
            "lng": resolved_lng,
        }
    }
