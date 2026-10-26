import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JsonType = sa.JSON().with_variant(JSONB, "postgresql")


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
