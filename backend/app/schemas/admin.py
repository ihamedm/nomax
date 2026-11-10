from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.user import UserRole


class AdminUserResponse(BaseModel):
    id: str
    phone: str
    national_id: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    permissions: list[str] = []
    is_verified: bool = False
    is_phone_verified: bool = False
    is_national_id_verified: bool = False
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class AdminUserCreate(BaseModel):
    phone: str = Field(..., min_length=8, max_length=13)
    full_name: Optional[str] = Field(None, max_length=120)
    national_id: Optional[str] = Field(None, min_length=10, max_length=10)
    # Keep "admin" as the API default for backwards compatibility with the
    # original create-admin endpoint; the dashboard always sends a role.
    role: UserRole = UserRole.ADMIN
    permissions: Optional[list[str]] = None
    is_verified: bool = False
    is_phone_verified: bool = False


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=120)
    national_id: Optional[str] = Field(None, min_length=10, max_length=10)
    role: Optional[UserRole] = None
    permissions: Optional[list[str]] = None
    is_verified: Optional[bool] = None
    is_phone_verified: Optional[bool] = None


class DevOtpResponse(BaseModel):
    phone: str
    otp: str
    expires_at: Optional[datetime] = None
