import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ad(Base):
    __tablename__ = "ads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    placement: Mapped[str] = mapped_column(String(40), nullable=False, default="home_banner", server_default="home_banner")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa.true())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
