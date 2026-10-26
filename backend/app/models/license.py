import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    license_number: Mapped[str] = mapped_column(String(80), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_verified_by_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa.false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
