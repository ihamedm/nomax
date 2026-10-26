import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SmsStatus:
    SENT = "sent"
    FAILED = "failed"


class SmsLog(Base):
    """One row per SMS provider attempt. Used for delivery auditing and support."""

    __tablename__ = "sms_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, nullable=False)
    phone: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, default="otp")
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
