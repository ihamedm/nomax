import re
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import require_permissions
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.ad import Ad
from app.models.category import Category, Subcategory
from app.models.tag import BusinessTag, Tag
from app.models.user import User
from app.schemas.category_suggestion import CategorySuggestionDiagnosticRequest
from app.services.category_suggestions import diagnose_category
from app.services import catalog_cache

router = APIRouter(tags=["cms"])


_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _clean_tag_list(raw: object) -> list[str]:
    """Trim, de-duplicate and validate a tag list or comma-separated string."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = re.split(r"[,،\n]", raw)
    if not isinstance(raw, (list, tuple, set)):
        raise AppError("validation_error", "tags_must_be_a_list", 422)
    names: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name or name in names:
            continue
        if len(name) > 60:
            raise AppError("validation_error", "tag_too_long", 422)
        names.append(name)
    return names


def _clean_visible_tags(raw: object, standard_tags: list[str]) -> list[str] | None:
    """Keep only tags that exist on the subcategory and enforce the UI limit."""
    if raw is None:
        return None
    allowed = set(standard_tags)
    names = [name for name in _clean_tag_list(raw) if name in allowed]
    if len(names) > settings.MAX_VISIBLE_SUBCATEGORY_TAGS:
        raise AppError(
            "validation_error",
            "too_many_visible_tags",
            422,
            {"max": settings.MAX_VISIBLE_SUBCATEGORY_TAGS},
        )
    return names


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
                "standard_tags": list(sub.standard_tags or []),
                "visible_tags": (
                    list(sub.visible_tags) if sub.visible_tags is not None else None
                ),
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


@router.post("/admin/categories/suggest/diagnose")
async def diagnose_category_suggestion(
    payload: CategorySuggestionDiagnosticRequest,
    actor: User = Depends(require_permissions("category.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Run the Laya pipeline with logs and tuning hints for the admin modal.

    Read-only: toggles affect this run only. Diagnostics sit behind the same
    permission as the categories page, and the Laya API key is never returned.
    """
    del actor
    result = await diagnose_category(
        session,
        payload.title,
        payload.description,
        rules_enabled=payload.rules_enabled,
        probe_laya=payload.probe_laya,
    )
    return {"data": result}


@router.post("/admin/categories")
async def create_category(
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
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
    await catalog_cache.invalidate_catalog(redis)
    await session.refresh(category)
    return {"data": _category_item(category, [])}


@router.patch("/admin/categories/{category_id}")
async def update_category(
    category_id: int,
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
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
    await catalog_cache.invalidate_catalog(redis)
    return {"data": _category_item(category, [])}


@router.delete("/admin/categories/{category_id}")
async def delete_category(
    category_id: int,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
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
    await catalog_cache.invalidate_catalog(redis)
    return {"data": {"id": category_id, "deleted": True}}


@router.post("/admin/subcategories")
async def create_subcategory(
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
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
    standard_tags = _clean_tag_list(payload.get("standard_tags"))
    sub = Subcategory(
        category_id=category.id,
        name=name,
        slug=slug,
        icon=payload.get("icon") or "❓",
        sort_order=int(payload.get("sort_order") or 0),
        standard_tags=standard_tags,
        visible_tags=_clean_visible_tags(payload.get("visible_tags"), standard_tags),
    )
    session.add(sub)
    await session.commit()
    await catalog_cache.invalidate_catalog(redis)
    await session.refresh(sub)
    return {"data": {"id": sub.id, "category_id": sub.category_id, "name": sub.name, "slug": sub.slug}}


@router.patch("/admin/subcategories/{subcategory_id}")
async def update_subcategory(
    subcategory_id: int,
    payload: dict,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
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
    if "standard_tags" in payload:
        payload["standard_tags"] = _clean_tag_list(payload["standard_tags"])
        if "visible_tags" not in payload:
            # Renaming/removing a tag must not leave it in the visible subset.
            payload["visible_tags"] = _clean_visible_tags(
                sub.visible_tags, payload["standard_tags"]
            )
    if "visible_tags" in payload:
        standard = payload.get("standard_tags", sub.standard_tags or [])
        payload["visible_tags"] = _clean_visible_tags(payload["visible_tags"], standard)
    for field in ("name", "slug", "icon", "sort_order", "standard_tags", "visible_tags", "category_id"):
        if field in payload:
            setattr(sub, field, payload[field])
    await session.commit()
    await catalog_cache.invalidate_catalog(redis)
    return {"data": {"id": sub.id, "category_id": sub.category_id, "name": sub.name, "slug": sub.slug}}


@router.post("/admin/subcategories/{subcategory_id}/sync-tags")
async def sync_subcategory_tags(
    subcategory_id: int,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Re-apply a subcategory's tag catalog to the businesses that serve it."""
    del actor
    sub = await session.get(Subcategory, subcategory_id)
    if sub is None or sub.deleted_at is not None:
        raise AppError("not_found", "subcategory_not_found", 404)

    from app.api.v1.businesses import _assign_tags
    from app.models.business import Business, BusinessSubcategory

    business_ids = set(
        (
            await session.execute(
                sa.select(BusinessSubcategory.business_id).where(
                    BusinessSubcategory.subcategory_id == subcategory_id
                )
            )
        ).scalars()
    )
    business_ids.update(
        (
            await session.execute(
                sa.select(Business.id).where(
                    Business.subcategory_id == subcategory_id,
                    Business.deleted_at.is_(None),
                )
            )
        ).scalars()
    )

    changed = added = removed = 0
    for business_id in business_ids:
        business = await session.get(Business, business_id)
        if business is None or business.deleted_at is not None:
            continue

        subcategory_ids = set(
            (
                await session.execute(
                    sa.select(BusinessSubcategory.subcategory_id).where(
                        BusinessSubcategory.business_id == business_id
                    )
                )
            ).scalars()
        )
        if business.subcategory_id is not None:
            subcategory_ids.add(business.subcategory_id)
        related = (
            await session.execute(
                sa.select(Subcategory).where(
                    Subcategory.id.in_(subcategory_ids),
                    Subcategory.deleted_at.is_(None),
                )
            )
        ).scalars().all()

        catalog: list[str] = []
        hidden_catalog: set[str] = set()
        for row in related:
            standard = list(row.standard_tags or [])
            for name in standard:
                if name not in catalog:
                    catalog.append(name)
            visible = (
                row.visible_tags
                if row.visible_tags is not None
                else standard[: settings.MAX_VISIBLE_SUBCATEGORY_TAGS]
            )
            visible_set = set(visible)
            hidden_catalog.update(name for name in standard if name not in visible_set)

        current = (
            await session.execute(
                sa.select(Tag.name, Tag.is_custom)
                .join(BusinessTag, BusinessTag.tag_id == Tag.id)
                .where(
                    BusinessTag.business_id == business_id,
                    Tag.deleted_at.is_(None),
                )
            )
        ).all()
        catalog_set = set(catalog)
        names: list[str] = []
        # Keep the owner's custom tags and the visible tags they picked.
        for name, is_custom in current:
            if (is_custom or name in catalog_set) and name not in names:
                names.append(name)
        # Search-only catalog tags are attached automatically.
        for name in catalog:
            if name in hidden_catalog and name not in names:
                names.append(name)

        before = {name for name, _ in current}
        after = set(names)
        if after != before:
            changed += 1
            added += len(after - before)
            removed += len(before - after)
        await _assign_tags(session, business_id, names, standard_names=set(catalog))

    await session.commit()
    return {"data": {"businesses": changed, "tags_added": added, "tags_removed": removed}}


@router.delete("/admin/subcategories/{subcategory_id}")
async def delete_subcategory(
    subcategory_id: int,
    actor: User = Depends(require_permissions("category.manage")),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    del actor
    sub = await session.get(Subcategory, subcategory_id)
    if sub is None or sub.deleted_at is not None:
        raise AppError("not_found", "subcategory_not_found", 404)
    sub.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    await catalog_cache.invalidate_catalog(redis)
    return {"data": {"id": subcategory_id, "deleted": True}}


@router.get("/admin/tags")
async def admin_list_tags(
    q: str | None = None,
    status: str | None = None,
    is_custom: bool | None = None,
    page: int = 1,
    per_page: int = Query(20, ge=1, le=100),
    actor: User = Depends(require_permissions("category.read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    page = max(1, page)
    conditions = [Tag.deleted_at.is_(None)]
    if status:
        conditions.append(Tag.status == status)
    if is_custom is not None:
        conditions.append(Tag.is_custom.is_(is_custom))
    if q and q.strip():
        conditions.append(Tag.name.ilike(f"%{q.strip()}%"))

    total = int(
        (await session.execute(sa.select(sa.func.count(Tag.id)).where(*conditions))).scalar()
        or 0
    )
    rows = (
        await session.execute(
            sa.select(Tag)
            .where(*conditions)
            .order_by(Tag.name, Tag.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).scalars().all()

    counts: dict[int, int] = {}
    tag_ids = [tag.id for tag in rows]
    if tag_ids:
        counts = dict(
            (
                await session.execute(
                    sa.select(BusinessTag.tag_id, sa.func.count(BusinessTag.business_id))
                    .where(BusinessTag.tag_id.in_(tag_ids))
                    .group_by(BusinessTag.tag_id)
                )
            ).all()
        )
    pages = max(1, (total + per_page - 1) // per_page)
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
        },
        "meta": {"page": page, "per_page": per_page, "total": total, "pages": pages},
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
