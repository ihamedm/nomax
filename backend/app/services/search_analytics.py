"""Search demand capture.

Only the first page of a search is logged. Category/subcategory are inferred
from the filter, the first result, or the query text so the market dashboard can
attribute keyword demand even when the user did not pick a category.
"""
from __future__ import annotations

import re

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import SearchLog
from app.models.business import Business
from app.models.category import Category, Subcategory
from app.models.user import User

_SPACES = re.compile(r"\s+")


def normalize_query(value: str | None) -> str | None:
    if not value:
        return None
    text = _SPACES.sub(" ", value.strip())[:160]
    return text or None


async def _infer_from_text(
    session: AsyncSession, query: str | None
) -> tuple[int | None, int | None]:
    if not query:
        return None, None
    lowered = query.lower()
    categories = (
        await session.execute(
            sa.select(Category.id, Category.name).where(Category.deleted_at.is_(None))
        )
    ).all()
    subs = (
        await session.execute(
            sa.select(
                Subcategory.id,
                Subcategory.category_id,
                Subcategory.name,
            ).where(Subcategory.deleted_at.is_(None))
        )
    ).all()

    best: tuple[int, int | None, int] | None = None
    for sub_id, category_id, name in subs:
        if name and name.lower() in lowered:
            score = len(name)
            if best is None or score > best[2]:
                best = (category_id, sub_id, score)
    if best is not None:
        return best[0], best[1]

    best_category: tuple[int, int] | None = None
    for category_id, name in categories:
        if name and name.lower() in lowered:
            score = len(name)
            if best_category is None or score > best_category[1]:
                best_category = (category_id, score)
    return (best_category[0] if best_category else None), None


async def log_search(
    session: AsyncSession,
    *,
    user: User | None,
    query: str | None,
    category_slug: str | None,
    subcategory_slug: str | None,
    results_count: int,
    first_business: Business | None,
) -> SearchLog | None:
    normalized = normalize_query(query)
    if not normalized and not category_slug and not subcategory_slug:
        return None

    category_id: int | None = None
    subcategory_id: int | None = None

    if category_slug:
        category_id = (
            await session.execute(
                sa.select(Category.id).where(
                    Category.slug == category_slug,
                    Category.deleted_at.is_(None),
                )
            )
        ).scalar()
    if subcategory_slug:
        row = (
            await session.execute(
                sa.select(Subcategory.id, Subcategory.category_id).where(
                    Subcategory.slug == subcategory_slug,
                    Subcategory.deleted_at.is_(None),
                )
            )
        ).first()
        if row is not None:
            subcategory_id, sub_category_id = row
            category_id = category_id or sub_category_id

    if category_id is None and first_business is not None:
        category_id = first_business.category_id
        subcategory_id = subcategory_id or first_business.subcategory_id

    if category_id is None:
        category_id, subcategory_id = await _infer_from_text(session, normalized)

    log = SearchLog(
        user_id=user.id if user is not None else None,
        query=normalized,
        normalized_query=normalized,
        category_id=category_id,
        subcategory_id=subcategory_id,
        results_count=max(0, results_count),
    )
    session.add(log)
    return log
