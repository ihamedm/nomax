"""Validated, dashboard-editable quote dispatch strategy.

The values live in `app_settings` under `quote_dispatch`. A database row is
optional: when absent the defaults below are the product behaviour. Validation
lives here so both the settings API and the dispatch engine agree on bounds.
"""
from __future__ import annotations

import sqlalchemy as sa
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import AppSetting

SETTING_KEY = "quote_dispatch"

TEHRAN_TZ = "Asia/Tehran"


class QuoteDispatchConfig(BaseModel):
    enabled: bool = True

    # How many owners each wave targets. A small first wave keeps the request
    # local; failed engagement expands to fresh owners.
    initial_batch_size: int = Field(3, ge=1, le=20)
    retry_batch_size: int = Field(2, ge=1, le=20)
    min_target_deliveries: int = Field(3, ge=1, le=20)
    max_rounds: int = Field(4, ge=1, le=10)

    # The worker checks engagement after this window. Silent waves (no seen and
    # no offer) always expand. Seen-but-no-offer is controlled by the toggle.
    response_window_minutes: int = Field(20, ge=5, le=1440)
    urgent_response_window_minutes: int = Field(5, ge=1, le=120)
    advance_on_seen: bool = True

    # Distance strategy: first the tight radius, then the expanded radius, then
    # (optionally) category-wide fallback so a request is never silently lost.
    dispatch_radius_km: float = Field(10, ge=0.5, le=100)
    expand_radius_km: float = Field(25, ge=1, le=200)
    subcategory_fallback: bool = True
    fallback_outside_radius: bool = True

    # Tehran-local sending window for normal (non-urgent) requests.
    day_start_hour: int = Field(6, ge=0, le=23)
    day_end_hour: int = Field(21, ge=1, le=24)
    allow_urgent_at_night: bool = True

    # When no approved business exists yet, keep searching (without burning a
    # delivery round) so owners approved later can still receive the request.
    no_candidate_retry_minutes: int = Field(30, ge=5, le=1440)

    @model_validator(mode="after")
    def _consistent_windows(self):
        if self.day_start_hour >= self.day_end_hour:
            raise ValueError("day_start_hour must be before day_end_hour")
        if self.expand_radius_km < self.dispatch_radius_km:
            raise ValueError("expand_radius_km must be >= dispatch_radius_km")
        return self


DEFAULT_QUOTE_DISPATCH = QuoteDispatchConfig().model_dump()


def normalize_dispatch_config(raw: dict | None) -> dict:
    """Merge partial values over defaults and return a validated dict."""
    candidate = {**DEFAULT_QUOTE_DISPATCH, **(raw or {})}
    try:
        return QuoteDispatchConfig.model_validate(candidate).model_dump()
    except ValidationError:
        return dict(DEFAULT_QUOTE_DISPATCH)


async def get_quote_dispatch_config(session: AsyncSession) -> QuoteDispatchConfig:
    row = await session.get(AppSetting, SETTING_KEY)
    raw = row.value if row is not None and isinstance(row.value, dict) else {}
    return QuoteDispatchConfig.model_validate(normalize_dispatch_config(raw))


async def save_quote_dispatch_config(
    session: AsyncSession, value: dict
) -> QuoteDispatchConfig:
    current = await get_quote_dispatch_config(session)
    merged = {**current.model_dump(), **(value or {})}
    config = QuoteDispatchConfig.model_validate(merged)
    row = await session.get(AppSetting, SETTING_KEY)
    if row is None:
        session.add(AppSetting(key=SETTING_KEY, value=config.model_dump()))
    else:
        row.value = config.model_dump()
    return config
