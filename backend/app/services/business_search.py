import base64
import math
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory

SORT_MODES = ("nearest", "top", "newest", "urgent")


@dataclass
class BusinessSearchParams:
    q: str | None = None
    category_slug: str | None = None
    subcategory_slug: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float = 10.0
    sort: str = "nearest"
    limit: int = 20
    offset: int = 0

    @property
    def has_coords(self) -> bool:
        return self.lat is not None and self.lng is not None


@dataclass
class BusinessHit:
    business: Business
    distance_m: float | None = None


@dataclass
class BusinessSearchPage:
    hits: list[BusinessHit]
    has_more: bool
    next_cursor: str | None


def encode_cursor(offset: int) -> str:
    raw = base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")
    return raw.rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        offset = int(base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("validation_error", "invalid_cursor", 422, {"cursor": cursor}) from exc
    if offset < 0:
        raise AppError("validation_error", "invalid_cursor", 422, {"cursor": cursor})
    return offset


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _base_conditions(params: BusinessSearchParams) -> list:
    conditions = [
        Business.status == BusinessStatus.APPROVED,
        Business.deleted_at.is_(None),
        Category.deleted_at.is_(None),
    ]
    if params.q:
        pattern = f"%{params.q.strip()}%"
        conditions.append(
            or_(
                Business.name.ilike(pattern),
                Business.short_description.ilike(pattern),
                Business.description.ilike(pattern),
                Business.address.ilike(pattern),
            )
        )
    if params.category_slug:
        conditions.append(Category.slug == params.category_slug)
    if params.subcategory_slug:
        conditions.append(Subcategory.slug == params.subcategory_slug)
    return conditions


def _base_select() -> sa.Select:
    return (
        select(Business)
        .join(Category, Business.category_id == Category.id)
        .outerjoin(Subcategory, Business.subcategory_id == Subcategory.id)
    )


def _order_without_geo(sort: str) -> list:
    if sort == "top":
        return [
            Business.rating_avg.desc().nullslast(),
            Business.rating_count.desc(),
            Business.id,
        ]
    if sort == "urgent":
        return [
            Business.is_24h.desc(),
            Business.rating_avg.desc(),
            Business.created_at.desc(),
            Business.id,
        ]
    # `nearest` without coordinates and `newest` both fall back to recency.
    return [Business.created_at.desc(), Business.id]


def _python_sort(hits: list[BusinessHit], sort: str, has_coords: bool) -> list[BusinessHit]:
    if sort == "top":
        return sorted(
            hits,
            key=lambda hit: (
                -(hit.business.rating_avg or 0),
                -(hit.business.rating_count or 0),
                str(hit.business.id),
            ),
        )
    if sort == "urgent":
        return sorted(
            hits,
            key=lambda hit: (
                not hit.business.is_24h,
                -(hit.business.rating_avg or 0),
                -_timestamp(hit.business.created_at),
                str(hit.business.id),
            ),
        )
    if sort == "nearest" and has_coords:
        return sorted(
            hits,
            key=lambda hit: (
                hit.distance_m if hit.distance_m is not None else float("inf"),
                -(hit.business.rating_avg or 0),
                str(hit.business.id),
            ),
        )
    return sorted(
        hits,
        key=lambda hit: (-_timestamp(hit.business.created_at), str(hit.business.id)),
    )


def _timestamp(value: datetime | None) -> float:
    if value is None:
        return 0.0
    try:
        return value.timestamp()
    except (OverflowError, OSError, ValueError):
        return 0.0


async def search_businesses(
    session: AsyncSession, params: BusinessSearchParams
) -> BusinessSearchPage:
    dialect = session.get_bind().dialect.name
    conditions = _base_conditions(params)

    if params.has_coords and dialect == "postgresql":
        return await _search_postgres(session, params, conditions)

    if params.has_coords and dialect != "postgresql":
        return await _search_in_memory(session, params, conditions)

    statement = (
        _base_select()
        .where(*conditions)
        .order_by(*_order_without_geo(params.sort))
        .limit(params.limit + 1)
        .offset(params.offset)
    )
    rows = (await session.execute(statement)).scalars().all()
    has_more = len(rows) > params.limit
    rows = rows[: params.limit]
    return BusinessSearchPage(
        hits=[BusinessHit(business=business) for business in rows],
        has_more=has_more,
        next_cursor=encode_cursor(params.offset + params.limit) if has_more else None,
    )


async def _search_postgres(
    session: AsyncSession, params: BusinessSearchParams, conditions: list
) -> BusinessSearchPage:
    # lat/lng/radius are validated floats (FastAPI Query), so embedding them
    # in the PostGIS expression is injection-safe and avoids fighting SQLAlchemy
    # for bind parameters inside a geography cast.
    point_sql = f"ST_SetSRID(ST_MakePoint({float(params.lng)!r}, {float(params.lat)!r}), 4326)::geography"
    distance_expr = sa.literal_column(f"ST_Distance(businesses.geo, {point_sql})")
    within_expr = sa.text(
        f"ST_DWithin(businesses.geo, {point_sql}, {float(params.radius_km) * 1000!r})"
    )

    statement = (
        _base_select()
        .add_columns(distance_expr.label("distance_m"))
        .where(*conditions, within_expr)
        .order_by(
            sa.text("distance_m ASC NULLS LAST"),
            Business.rating_avg.desc(),
            Business.id,
        )
        .limit(params.limit + 1)
        .offset(params.offset)
    )
    if params.sort == "top":
        statement = statement.order_by(None).order_by(
            Business.rating_avg.desc(), Business.rating_count.desc(), Business.id
        )
    elif params.sort == "newest":
        statement = statement.order_by(None).order_by(Business.created_at.desc(), Business.id)
    elif params.sort == "urgent":
        statement = statement.order_by(None).order_by(
            Business.is_24h.desc(), Business.rating_avg.desc(), Business.id
        )

    rows = (await session.execute(statement)).all()
    has_more = len(rows) > params.limit
    rows = rows[: params.limit]
    return BusinessSearchPage(
        hits=[
            BusinessHit(business=business, distance_m=distance)
            for business, distance in rows
        ],
        has_more=has_more,
        next_cursor=encode_cursor(params.offset + params.limit) if has_more else None,
    )


async def _search_in_memory(
    session: AsyncSession, params: BusinessSearchParams, conditions: list
) -> BusinessSearchPage:
    """SQLite/test fallback: filter and sort in Python.

    Production always runs on Postgres and uses the indexed PostGIS path.
    """

    statement = _base_select().where(*conditions)
    businesses = (await session.execute(statement)).scalars().all()

    hits: list[BusinessHit] = []
    radius_m = params.radius_km * 1000
    for business in businesses:
        if business.geo_lat is None or business.geo_lng is None:
            continue
        distance = haversine_m(params.lat, params.lng, business.geo_lat, business.geo_lng)
        if distance <= radius_m:
            hits.append(BusinessHit(business=business, distance_m=distance))

    ordered = _python_sort(hits, params.sort, params.has_coords)
    window = ordered[params.offset : params.offset + params.limit + 1]
    has_more = len(window) > params.limit
    window = window[: params.limit]
    return BusinessSearchPage(
        hits=window,
        has_more=has_more,
        next_cursor=encode_cursor(params.offset + params.limit) if has_more else None,
    )
