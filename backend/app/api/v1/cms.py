import re
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.core.errors import AppError
from app.db.session import get_db
from app.models.ad import Ad
from app.models.category import Category, Subcategory
from app.models.tag import BusinessTag, Tag
from app.models.user import User

router = APIRouter(tags=["cms"])


_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _slug(prefix: str, payload: dict, *, required: bool = False) -> str:
    raw = (payload.get("slug") or "").strip().lower()
    if not raw:
        if required:
            raise AppError("validation_error", "slug_required", 422)
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    if not _SLUG_PATTERN.fullmatch(raw):
        raise AppError("validation_error", "invalid_slug", 422)
    return raw


async def _ensure_category_slug_free(
    session: AsyncSession, slug: str, *, exclude_id: int | None = None
) -> None:
    stmt = sa.select(Category.id).where(Category.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    if (await session.execute(stmt)).scalars().first() is not None:
        raise AppError("conflict", "category_slug_already_exists", 409)


async def _ensure_subcategory_slug_free(
    session: AsyncSession,
    slug: str,
    category_id: int,
    *,
    exclude_id: int | None = None,
) -> None:
    stmt = sa.select(Subcategory.id).where(
        Subcategory.slug == slug, Subcategory.category_id == category_id
    )
    if exclude_id is not None:
        stmt = stmt.where(Subcategory.id != exclude_id)
    if (await session.execute(stmt)).scalars().first() is not None:
        raise AppError("conflict", "subcategory_slug_already_exists", 409)


def _category_item(category: Category, subcategories: list[Subcategory]) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "icon": category.icon,
        "sort_order": category.sort_order,
        "is_active": category.is_active,
        "subcategories": [
            {
                "id": sub.id,
                "category_id": sub.category_id,
                "name": sub.name,
                "slug": sub.slug,
                "icon": sub.icon,
                "sort_order": sub.sort_order,
            }
            for sub in subcategories
        ],
    }


@router.get("/admin/categories")
async def admin_list_categories(
    actor: User = Depends(require_permissions("category.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    categories = (
        await session.execute(
            sa.select(Category).where(Category.deleted_at.is_(None)).order_by(Category.sort_order, Category.id)
        )
    ).scalars().all()
    subcategories = (
        await session.execute(
            sa.select(Subcategory).where(Subcategory.deleted_at.is_(None)).order_by(Subcategory.sort_order, Subcategory.id)
        )
    ).scalars().all()
    by_category: dict[int, list[Subcategory]] = {}
    for sub in subcategories:
        by_category.setdefault(sub.category_id, []).append(sub)
    return {"data": {"items": [_category_item(cat, by_category.get(cat.id, [])) for cat in categories]}}


@router.post("/admin/categories")
async def create_category(
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    name = (payload.get("name") or "").strip()
    if not name:
        raise AppError("validation_error", "name_required", 422)
    slug = _slug("category", payload)
    await _ensure_category_slug_free(session, slug)
    category = Category(
        name=name,
        slug=slug,
        icon=payload.get("icon") or "❓",
        sort_order=int(payload.get("sort_order") or 0),
        is_active=bool(payload.get("is_active", True)),
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return {"data": _category_item(category, [])}


@router.patch("/admin/categories/{category_id}")
async def update_category(
    category_id: int,
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    category = await session.get(Category, category_id)
    if category is None or category.deleted_at is not None:
        raise AppError("not_found", "category_not_found", 404)
    if "slug" in payload:
        payload["slug"] = _slug("category", payload, required=True)
        await _ensure_category_slug_free(session, payload["slug"], exclude_id=category.id)
    for field in ("name", "slug", "icon", "sort_order", "is_active"):
        if field in payload:
            setattr(category, field, payload[field])
    await session.commit()
    return {"data": _category_item(category, [])}


@router.delete("/admin/categories/{category_id}")
async def delete_category(
    category_id: int,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    category = await session.get(Category, category_id)
    if category is None or category.deleted_at is not None:
        raise AppError("not_found", "category_not_found", 404)
    category.deleted_at = datetime.now(timezone.utc)
    await session.execute(
        sa.update(Subcategory)
        .where(Subcategory.category_id == category_id, Subcategory.deleted_at.is_(None))
        .values(deleted_at=datetime.now(timezone.utc))
    )
    await session.commit()
    return {"data": {"id": category_id, "deleted": True}}


@router.post("/admin/subcategories")
async def create_subcategory(
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    name = (payload.get("name") or "").strip()
    if not name or payload.get("category_id") is None:
        raise AppError("validation_error", "name_category_required", 422)
    category = await session.get(Category, payload["category_id"])
    if category is None or category.deleted_at is not None:
        raise AppError("not_found", "category_not_found", 404)
    slug = _slug("subcategory", payload)
    await _ensure_subcategory_slug_free(session, slug, category.id)
    sub = Subcategory(
        category_id=category.id,
        name=name,
        slug=slug,
        icon=payload.get("icon") or "❓",
        sort_order=int(payload.get("sort_order") or 0),
        standard_tags=payload.get("standard_tags") or [],
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return {"data": {"id": sub.id, "category_id": sub.category_id, "name": sub.name, "slug": sub.slug}}


@router.patch("/admin/subcategories/{subcategory_id}")
async def update_subcategory(
    subcategory_id: int,
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    sub = await session.get(Subcategory, subcategory_id)
    if sub is None or sub.deleted_at is not None:
        raise AppError("not_found", "subcategory_not_found", 404)
    if "slug" in payload:
        payload["slug"] = _slug("subcategory", payload, required=True)
        await _ensure_subcategory_slug_free(
            session,
            payload["slug"],
            int(payload.get("category_id") or sub.category_id),
            exclude_id=sub.id,
        )
    for field in ("name", "slug", "icon", "sort_order", "standard_tags", "category_id"):
        if field in payload:
            setattr(sub, field, payload[field])
    await session.commit()
    return {"data": {"id": sub.id, "category_id": sub.category_id, "name": sub.name, "slug": sub.slug}}


@router.delete("/admin/subcategories/{subcategory_id}")
async def delete_subcategory(
    subcategory_id: int,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    sub = await session.get(Subcategory, subcategory_id)
    if sub is None or sub.deleted_at is not None:
        raise AppError("not_found", "subcategory_not_found", 404)
    sub.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    return {"data": {"id": subcategory_id, "deleted": True}}


@router.get("/admin/tags")
async def admin_list_tags(
    actor: User = Depends(require_permissions("category.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    counts = dict(
        (
            await session.execute(
                sa.select(BusinessTag.tag_id, sa.func.count(BusinessTag.business_id)).group_by(BusinessTag.tag_id)
            )
        ).all()
    )
    rows = (
        await session.execute(
            sa.select(Tag).where(Tag.deleted_at.is_(None)).order_by(Tag.name)
        )
    ).scalars().all()
    return {
        "data": {
            "items": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "status": tag.status,
                    "is_custom": tag.is_custom,
                    "usage_count": counts.get(tag.id, 0),
                }
                for tag in rows
            ]
        }
    }


@router.post("/admin/tags")
async def create_tag(
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    name = (payload.get("name") or "").strip()
    if not name:
        raise AppError("validation_error", "name_required", 422)
    existing = (await session.execute(sa.select(Tag).where(Tag.name == name))).scalars().first()
    if existing is not None:
        raise AppError("conflict", "tag_already_exists", 409)
    tag = Tag(name=name, is_custom=bool(payload.get("is_custom", True)), status=payload.get("status", "approved"))
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return {"data": {"id": tag.id, "name": tag.name, "status": tag.status, "is_custom": tag.is_custom, "usage_count": 0}}


@router.patch("/admin/tags/{tag_id}")
async def update_tag(
    tag_id: int,
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    tag = await session.get(Tag, tag_id)
    if tag is None or tag.deleted_at is not None:
        raise AppError("not_found", "tag_not_found", 404)
    for field in ("name", "status", "is_custom"):
        if field in payload:
            setattr(tag, field, payload[field])
    await session.commit()
    return {"data": {"id": tag.id, "name": tag.name, "status": tag.status, "is_custom": tag.is_custom}}


@router.delete("/admin/tags/{tag_id}")
async def delete_tag(
    tag_id: int,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    tag = await session.get(Tag, tag_id)
    if tag is None or tag.deleted_at is not None:
        raise AppError("not_found", "tag_not_found", 404)
    tag.deleted_at = datetime.now(timezone.utc)
    await session.execute(sa.delete(BusinessTag).where(BusinessTag.tag_id == tag_id))
    await session.commit()
    return {"data": {"id": tag_id, "deleted": True}}


@router.get("/admin/ads")
async def admin_list_ads(
    actor: User = Depends(require_permissions("ad.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    rows = (
        await session.execute(
            sa.select(Ad).where(Ad.deleted_at.is_(None)).order_by(Ad.created_at.desc())
        )
    ).scalars().all()
    return {
        "data": {
            "items": [
                {
                    "id": str(ad.id),
                    "title": ad.title,
                    "body": ad.body,
                    "image_url": ad.image_url,
                    "target_url": ad.target_url,
                    "placement": ad.placement,
                    "is_active": ad.is_active,
                    "created_at": ad.created_at.isoformat() if ad.created_at else None,
                }
                for ad in rows
            ]
        }
    }


@router.post("/admin/ads")
async def admin_create_ad(
    payload: dict,
    actor: User = Depends(require_permissions("ad.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    title = (payload.get("title") or "").strip()
    if not title:
        raise AppError("validation_error", "title_required", 422)
    ad = Ad(
        title=title,
        body=payload.get("body"),
        image_url=payload.get("image_url"),
        target_url=payload.get("target_url"),
        placement=payload.get("placement") or "home_banner",
        is_active=bool(payload.get("is_active", True)),
    )
    session.add(ad)
    await session.commit()
    await session.refresh(ad)
    return {"data": {"id": str(ad.id)}}


@router.patch("/admin/ads/{ad_id}")
async def admin_update_ad(
    ad_id: str,
    payload: dict,
    actor: User = Depends(require_permissions("ad.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    try:
        ad = await session.get(Ad, uuid.UUID(ad_id))
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    if ad is None or ad.deleted_at is not None:
        raise AppError("not_found", "ad_not_found", 404)
    for field in ("title", "body", "image_url", "target_url", "placement", "is_active"):
        if field in payload:
            setattr(ad, field, payload[field])
    await session.commit()
    return {"data": {"id": str(ad.id)}}


@router.delete("/admin/ads/{ad_id}")
async def admin_delete_ad(
    ad_id: str,
    actor: User = Depends(require_permissions("ad.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    try:
        ad = await session.get(Ad, uuid.UUID(ad_id))
    except ValueError:
        raise AppError("validation_error", "invalid_id", 422)
    if ad is None or ad.deleted_at is not None:
        raise AppError("not_found", "ad_not_found", 404)
    ad.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    return {"data": {"id": ad_id, "deleted": True}}
