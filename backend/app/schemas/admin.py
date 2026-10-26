from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.user import UserRole


class AdminUserResponse(BaseModel):
    id: str
    phone: str
    full_name: Optional[str] = None
    role: str
    permissions: list[str] = []
    is_phone_verified: bool = False
    created_at: Optional[datetime] = None


class AdminUserUpdate(BaseModel):
    role: Optional[UserRole] = None
    permissions: Optional[list[str]] = None


class DevOtpResponse(BaseModel):
    phone: str
    otp: str
    expires_at: Optional[datetime] = None
