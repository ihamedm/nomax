import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_review_business_user"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_name: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
