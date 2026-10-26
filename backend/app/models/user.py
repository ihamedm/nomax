import uuid
from datetime import datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, Enum):
    CUSTOMER = "customer"
    OWNER = "owner"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, nullable=False)
    phone: Mapped[str] = mapped_column(String(11), nullable=False, unique=True, index=True)
    national_id: Mapped[str | None] = mapped_column(String(10), nullable=True, unique=True)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        sa.Enum(
            UserRole,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserRole.CUSTOMER,
        server_default=UserRole.CUSTOMER.value,
    )
    permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default=sa.text("'[]'"))
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa.false())
    is_national_id_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa.false())
    national_id_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def has_permission(self, code: str) -> bool:
        if self.role == UserRole.SUPERADMIN:
            return True
        return code in (self.permissions or [])
