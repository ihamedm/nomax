import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuoteRequest(Base):
    __tablename__ = "quote_requests"
    __table_args__ = (
        # One active request per customer.
        sa.Index(
            "uq_quote_active_per_user",
            "customer_id",
            unique=True,
            sqlite_where=sa.text("status = 'active'"),
            postgresql_where=sa.text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    neighborhood: Mapped[str | None] = mapped_column(String(120), nullable=True)
    geo_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa.false())
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_offer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    phone_revealed_to: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (sa.UniqueConstraint("business_id", "request_id", name="uq_offer_business_request"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quote_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    price: Mapped[float | None] = mapped_column(Numeric(12, 0), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
