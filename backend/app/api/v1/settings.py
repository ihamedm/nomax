import sqlalchemy as sa
from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.core.errors import AppError
from app.db.session import get_db
from app.models.setting import AppSetting
from app.models.user import User
from app.services.quote_dispatch_settings import (
    DEFAULT_QUOTE_DISPATCH,
    get_quote_dispatch_config,
    save_quote_dispatch_config,
)

router = APIRouter(tags=["settings"])

DEFAULT_TRENDING = [
    "تعمیر کولر",
    "لوله‌کشی",
    "برق‌کاری",
    "تعمیر خودرو",
    "نظافت منزل",
]


async def _values(session: AsyncSession) -> dict:
    rows = (await session.execute(sa.select(AppSetting))).scalars().all()
    return {row.key: row.value for row in rows}


@router.get("/search/trending")
async def trending_searches(session: AsyncSession = Depends(get_db)) -> dict:
    values = await _values(session)
    items = values.get("search_trends") or DEFAULT_TRENDING
    return {"data": {"items": list(items)}}


@router.get("/admin/settings")
async def get_settings(
    actor: User = Depends(require_permissions("admin.settings.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    values = await _values(session)
    dispatch = await get_quote_dispatch_config(session)
    return {
        "data": {
            "search_trends": values.get("search_trends") or DEFAULT_TRENDING,
            "quote_dispatch": dispatch.model_dump(),
            "quote_dispatch_defaults": DEFAULT_QUOTE_DISPATCH,
        }
    }


@router.put("/admin/settings/{key}")
async def update_setting(
    key: str,
    payload: dict,
    actor: User = Depends(require_permissions("admin.settings.manage")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    if key == "search_trends":
        raw = payload.get("value")
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise AppError("validation_error", "value_must_be_string_list", 422)
        value = [item.strip() for item in raw if item.strip()]
        setting = await session.get(AppSetting, key)
        if setting is None:
            setting = AppSetting(key=key, value=value)
            session.add(setting)
        else:
            setting.value = value
        await session.commit()
        return {"data": {"key": key, "value": value}}

    if key == "quote_dispatch":
        raw = payload.get("value")
        if not isinstance(raw, dict):
            raise AppError("validation_error", "value_must_be_object", 422)
        try:
            config = await save_quote_dispatch_config(session, raw)
        except ValidationError as exc:
            raise AppError(
                "validation_error",
                "invalid_dispatch_settings",
                422,
                {"errors": str(exc).splitlines()[:6]},
            )
        await session.commit()
        return {"data": {"key": key, "value": config.model_dump()}}

    raise AppError("not_found", "setting_not_found", 404)
