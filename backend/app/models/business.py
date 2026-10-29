import uuid
from datetime import datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BusinessStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint("geo_lat IS NULL OR (geo_lat BETWEEN -90 AND 90)", name="ck_business_geo_lat"),
        CheckConstraint(
            "geo_lng IS NULL OR (geo_lng BETWEEN -180 AND 180)", name="ck_business_geo_lng"
        ),
        CheckConstraint("rating_avg >= 0 AND rating_avg <= 5", name="ck_business_rating_avg"),
        CheckConstraint("rating_count >= 0", name="ck_business_rating_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subcategory_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcategories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    short_description: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_business: Mapped[str | None] = mapped_column(String(11), nullable=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    # Coordinates are the source of truth. Postgres adds a generated PostGIS
    # `geo` geography column + GIST index in migration 0003 for radius search;
    # keeping the ORM free of a GIS type lets the test suite run on SQLite.
    geo_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    instagram: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_24h: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa.false())
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa.false())
    status: Mapped[BusinessStatus] = mapped_column(
        sa.Enum(
            BusinessStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=BusinessStatus.PENDING,
        server_default=BusinessStatus.PENDING.value,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rating_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default=sa.text("0"))
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sa.text("0"))
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sa.text("0"))
    profile_image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped["Category"] = relationship(lazy="joined")
    subcategory: Mapped["Subcategory | None"] = relationship(lazy="joined")
