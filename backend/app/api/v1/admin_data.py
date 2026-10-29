"""Generic superadmin data browser/editor for the remaining database models.

The specialised screens (businesses, categories, tags, ads, users) cover the
high-traffic models. This router exposes every other content table so a
superadmin can still inspect and CRUD records from the dashboard.
"""

import json
import uuid
from datetime import date, datetime
from enum import Enum

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_superadmin
from app.core.errors import AppError
from app.db.session import get_db
from app.models.category import Subcategory
from app.models.contact import ContactMessage
from app.models.job import ScheduledJob
from app.models.license import License
from app.models.notification import DeviceToken, Notification, NotificationDelivery
from app.models.quote import Offer, QuoteRequest
from app.models.review import Review
from app.models.sms import SmsLog
from app.models.suggestion import CategorySuggestion
from app.models.user import User

router = APIRouter(tags=["admin-data"], prefix="/admin/data")

REGISTRY: dict[str, tuple[type, str]] = {
    "subcategories": (Subcategory, "زیردسته‌ها"),
    "reviews": (Review, "نظرات"),
    "quote_requests": (QuoteRequest, "درخواست‌های قیمت"),
    "offers": (Offer, "پیشنهادهای قیمت"),
    "category_suggestions": (CategorySuggestion, "پیشنهاد دسته‌بندی"),
    "contact_messages": (ContactMessage, "پیام‌های تماس"),
    "licenses": (License, "مجوزها"),
    "notifications": (Notification, "اعلان‌ها"),
    "device_tokens": (DeviceToken, "دستگاه‌ها"),
    "notification_deliveries": (NotificationDelivery, "تحویل اعلان"),
    "scheduled_jobs": (ScheduledJob, "کارهای زمان‌بندی‌شده"),
    "sms_logs": (SmsLog, "لاگ پیامک"),
}

JSON_TYPES = (sa.JSON,)
DATETIME_TYPES = (sa.DateTime,)
BOOL_TYPES = (sa.Boolean,)
INT_TYPES = (sa.Integer, sa.BigInteger, sa.SmallInteger)
FLOAT_TYPES = (sa.Float, sa.Numeric)


def _model(name: str):
    entry = REGISTRY.get(name)
    if entry is None:
        raise AppError("not_found", "model_not_found", 404)
    return entry[0]


def _kind(column) -> str:
    type_ = column.type
    if isinstance(type_, BOOL_TYPES):
        return "boolean"
    if isinstance(type_, INT_TYPES):
        return "number"
    if isinstance(type_, FLOAT_TYPES):
        return "number"
    if isinstance(type_, DATETIME_TYPES):
        return "datetime"
    if isinstance(type_, JSON_TYPES):
        return "json"
    return "string"


def _columns(model) -> list[dict]:
    mapper = sa.inspect(model)
    return [
        {
            "name": column.key,
            "kind": _kind(column),
            "nullable": bool(column.nullable),
            "primary_key": bool(column.primary_key),
        }
        for column in mapper.columns
        if column.key != "hashed_password"
    ]


def _coerce(column, value):
    if value is None or value == "":
        return None
    if isinstance(column.type, BOOL_TYPES):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("1", "true", "yes", "on")
    if isinstance(column.type, INT_TYPES):
        return int(value)
    if isinstance(column.type, FLOAT_TYPES):
        return float(value)
    if isinstance(column.type, DATETIME_TYPES):
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if isinstance(column.type, JSON_TYPES):
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)
    if isinstance(column.type, sa.Uuid):
        return uuid.UUID(str(value))
    return str(value)


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _serialize(row) -> dict:
    mapper = sa.inspect(type(row))
    return {column.key: _json_value(getattr(row, column.key)) for column in mapper.columns}


def _pk_column(model):
    mapper = sa.inspect(model)
    primary_keys = list(mapper.primary_key)
    if len(primary_keys) != 1:
        raise AppError("validation_error", "composite_primary_key_not_supported", 422)
    return mapper.columns[primary_keys[0].key]


def _pk_value(column, raw: str):
    if isinstance(column.type, sa.Uuid):
        try:
            return uuid.UUID(raw)
        except ValueError:
            raise AppError("validation_error", "invalid_id", 422)
    if isinstance(column.type, INT_TYPES):
        try:
            return int(raw)
        except ValueError:
            raise AppError("validation_error", "invalid_id", 422)
    return raw


@router.get("/models")
async def list_models(
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    items = []
    for name, (model, label) in REGISTRY.items():
        count = int(
            (await session.execute(sa.select(sa.func.count()).select_from(model))).scalar() or 0
        )
        items.append({"name": name, "label": label, "count": count, "columns": _columns(model)})
    return {"data": {"items": items}}


@router.get("/{name}")
async def list_rows(
    name: str,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    model = _model(name)
    mapper = sa.inspect(model)
    limit = min(200, max(1, limit))
    statement = sa.select(model)
    if q:
        term = f"%{q.strip()}%"
        string_columns = [
            column
            for column in mapper.columns
            if isinstance(column.type, (sa.String, sa.Text))
        ]
        if string_columns:
            statement = statement.where(
                sa.or_(*[column.ilike(term) for column in string_columns])
            )
    pk = _pk_column(model)
    total = int(
        (await session.execute(sa.select(sa.func.count()).select_from(statement.subquery()))).scalar()
        or 0
    )
    rows = (
        await session.execute(statement.order_by(pk.desc()).offset(offset).limit(limit))
    ).scalars().all()
    return {
        "data": {"items": [_serialize(row) for row in rows], "columns": _columns(model)},
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.post("/{name}")
async def create_row(
    name: str,
    payload: dict,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    model = _model(name)
    mapper = sa.inspect(model)
    values = {}
    for column in mapper.columns:
        if column.key in payload and column.key != "hashed_password":
            values[column.key] = _coerce(column, payload[column.key])
    try:
        row = model(**values)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    except (IntegrityError, ValueError, TypeError, json.JSONDecodeError) as exc:
        await session.rollback()
        raise AppError("validation_error", "record_not_saved", 422, {"detail": str(exc)})
    return {"data": _serialize(row)}


@router.patch("/{name}/{pk}")
async def update_row(
    name: str,
    pk: str,
    payload: dict,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    model = _model(name)
    mapper = sa.inspect(model)
    pk_column = _pk_column(model)
    row = await session.get(model, _pk_value(pk_column, pk))
    if row is None:
        raise AppError("not_found", "record_not_found", 404)
    try:
        for column in mapper.columns:
            if column.key in payload and not column.primary_key and column.key != "hashed_password":
                setattr(row, column.key, _coerce(column, payload[column.key]))
        await session.commit()
        await session.refresh(row)
    except (IntegrityError, ValueError, TypeError, json.JSONDecodeError) as exc:
        await session.rollback()
        raise AppError("validation_error", "record_not_saved", 422, {"detail": str(exc)})
    return {"data": _serialize(row)}


@router.delete("/{name}/{pk}")
async def delete_row(
    name: str,
    pk: str,
    actor: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    del actor
    model = _model(name)
    pk_column = _pk_column(model)
    row = await session.get(model, _pk_value(pk_column, pk))
    if row is None:
        raise AppError("not_found", "record_not_found", 404)
    try:
        await session.delete(row)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError("conflict", "record_in_use", 409, {"detail": str(exc)})
    return {"data": {"deleted": True}}
