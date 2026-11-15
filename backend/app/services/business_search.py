import base64
import math
import re
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.business import Business, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.tag import BusinessTag, Tag
from app.models.user import User

SORT_MODES = ("nearest", "top", "newest", "urgent", "visited")


@dataclass
class BusinessSearchParams:
    q: str | None = None
    category_slug: str | None = None
    subcategory_slug: str | None = None
    lat: float | None = None
    lng: float | None = None
    # ``None`` means "no distance cap": results are still ordered by distance
    # for the ``nearest`` sort, but businesses outside any radius are returned
    # too. A caller opts into a hard cap by sending an explicit radius.
    radius_km: float | None = None
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


def _q_term(params: BusinessSearchParams) -> str | None:
    if not params.q:
        return None
    return params.q.strip() or None


# Phones are stored without the leading 0/98, and users type them in Persian
# digits on mobile keyboards, so match on the normalized digits.
_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _phone_digits(term: str) -> str | None:
    compact = re.sub(r"[\s\-()+.]", "", term.translate(_DIGIT_TRANSLATION))
    if not compact.isdigit():
        return None
    if compact.startswith("98") and len(compact) > 10:
        compact = compact[2:]
    digits = compact.lstrip("0")
    return digits or None


def _tag_match(pattern: str):
    return (
        sa.select(BusinessTag.business_id)
        .join(Tag, Tag.id == BusinessTag.tag_id)
        .where(
            BusinessTag.business_id == Business.id,
            Tag.deleted_at.is_(None),
            Tag.name.ilike(pattern),
        )
        .exists()
    )


def _relevance_rank(params: BusinessSearchParams):
    """Order matches the way people search: name first, then tags and
    descriptions (equally), then the incidental fields (address, phone, owner).
    """
    term = _q_term(params)
    if term is None:
        return None
    pattern = f"%{term}%"
    return sa.case(
        (Business.name.ilike(pattern), 0),
        (
            or_(
                Business.short_description.ilike(pattern),
                Business.description.ilike(pattern),
                _tag_match(pattern),
            ),
            1,
        ),
        else_=2,
    )


def _base_conditions(params: BusinessSearchParams) -> list:
    conditions = [
        Business.status == BusinessStatus.APPROVED,
        Business.deleted_at.is_(None),
        Category.deleted_at.is_(None),
    ]
    term = _q_term(params)
    if term is not None:
        pattern = f"%{term}%"
        clauses = [
            Business.name.ilike(pattern),
            Business.short_description.ilike(pattern),
            Business.description.ilike(pattern),
            Business.address.ilike(pattern),
            Business.phone_business.ilike(pattern),
            User.full_name.ilike(pattern),
            User.phone.ilike(pattern),
            _tag_match(pattern),
        ]
        digits = _phone_digits(term)
        if digits is not None:
            # Accept «۰۹…», «09…», «+989…» and «98…» for both phones.
            clauses.append(Business.phone_business.ilike(f"%{digits}%"))
            clauses.append(User.phone.ilike(f"%{digits}%"))
        conditions.append(or_(*clauses))
    if params.category_slug:
        conditions.append(Category.slug == params.category_slug)
    if params.subcategory_slug:
        # A business can serve several subcategories of its category; match any
        # of them, with the legacy single column still honoured.
        conditions.append(
            or_(
                Subcategory.slug == params.subcategory_slug,
                Business.subcategories.any(Subcategory.slug == params.subcategory_slug),
            )
        )
    return conditions


def _base_select() -> sa.Select:
    return (
        select(Business)
        .join(Category, Business.category_id == Category.id)
        .join(User, Business.owner_id == User.id)
        .outerjoin(Subcategory, Business.subcategory_id == Subcategory.id)
    )


def _order_by(sort: str, distance_expr=None) -> list:
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
    if sort == "visited":
        return [Business.view_count.desc(), Business.rating_avg.desc(), Business.id]
    if sort == "nearest" and distance_expr is not None:
        return [distance_expr.asc().nullslast(), Business.rating_avg.desc(), Business.id]
    # `nearest` without coordinates and `newest` both fall back to recency.
    return [Business.created_at.desc(), Business.id]


def _ordered_for(params: BusinessSearchParams, distance_expr=None) -> list:
    """Relevance first when searching, so the chosen sort only breaks ties."""
    rank = _relevance_rank(params)
    order = _order_by(params.sort, distance_expr)
    return [rank, *order] if rank is not None else order


def _relevance_tier(
    business: Business, term: str | None, tag_names: list[str]
) -> int:
    if term is None:
        return 0
    needle = term.casefold()
    if needle in (business.name or "").casefold():
        return 0
    if needle in (business.short_description or "").casefold() or needle in (
        business.description or ""
    ).casefold():
        return 1
    if any(needle in name for name in tag_names):
        return 1
    return 2


def _python_sort(
    hits: list[BusinessHit],
    params: BusinessSearchParams,
    tag_names: dict,
) -> list[BusinessHit]:
    term = _q_term(params)
    sort = params.sort
    has_coords = params.has_coords

    def tier(hit: BusinessHit) -> int:
        return _relevance_tier(hit.business, term, tag_names.get(hit.business.id, []))

    if sort == "top":
        key = lambda hit: (
            tier(hit),
            -(hit.business.rating_avg or 0),
            -(hit.business.rating_count or 0),
            str(hit.business.id),
        )
    elif sort == "urgent":
        key = lambda hit: (
            tier(hit),
            not hit.business.is_24h,
            -(hit.business.rating_avg or 0),
            -_timestamp(hit.business.created_at),
            str(hit.business.id),
        )
    elif sort == "visited":
        key = lambda hit: (
            tier(hit),
            -(hit.business.view_count or 0),
            -(hit.business.rating_avg or 0),
            str(hit.business.id),
        )
    elif sort == "nearest" and has_coords:
        key = lambda hit: (
            tier(hit),
            hit.distance_m if hit.distance_m is not None else float("inf"),
            -(hit.business.rating_avg or 0),
            str(hit.business.id),
        )
    else:
        key = lambda hit: (
            tier(hit),
            -_timestamp(hit.business.created_at),
            str(hit.business.id),
        )
    return sorted(hits, key=key)


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
        .order_by(*_ordered_for(params))
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

    statement = (
        _base_select()
        .add_columns(distance_expr.label("distance_m"))
        .where(*conditions)
        .order_by(*_ordered_for(params, distance_expr))
        .limit(params.limit + 1)
        .offset(params.offset)
    )
    if params.radius_km is not None:
        # Only cap the results when the caller explicitly asked for a radius.
        within_expr = sa.text(
            f"ST_DWithin(businesses.geo, {point_sql}, {float(params.radius_km) * 1000!r})"
        )
        statement = statement.where(within_expr)

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
    radius_m = params.radius_km * 1000 if params.radius_km is not None else None
    for business in businesses:
        distance = (
            haversine_m(params.lat, params.lng, business.geo_lat, business.geo_lng)
            if business.geo_lat is not None and business.geo_lng is not None
            else None
        )
        # Without an explicit radius, businesses missing coordinates are kept
        # (they simply sort last for the `nearest` mode) so a small city doesn't
        # lose rows that were created before geo data existed.
        if radius_m is not None and (distance is None or distance > radius_m):
            continue
        hits.append(BusinessHit(business=business, distance_m=distance))

    tag_names: dict = {}
    term = _q_term(params)
    if term is not None and hits:
        rows = await session.execute(
            select(BusinessTag.business_id, Tag.name)
            .join(Tag, Tag.id == BusinessTag.tag_id)
            .where(
                BusinessTag.business_id.in_([hit.business.id for hit in hits]),
                Tag.deleted_at.is_(None),
            )
        )
        for business_id, name in rows:
            tag_names.setdefault(business_id, []).append(name.casefold())

    ordered = _python_sort(hits, params, tag_names)
    window = ordered[params.offset : params.offset + params.limit + 1]
    has_more = len(window) > params.limit
    window = window[: params.limit]
    return BusinessSearchPage(
        hits=window,
        has_more=has_more,
        next_cursor=encode_cursor(params.offset + params.limit) if has_more else None,
    )
