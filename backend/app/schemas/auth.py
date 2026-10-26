from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OtpRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=13)


class OtpVerify(BaseModel):
    phone: str = Field(..., min_length=8, max_length=13)
    code: str = Field(..., min_length=6, max_length=6)
    national_id: Optional[str] = Field(None, min_length=10, max_length=10)


class RefreshRequest(BaseModel):
    refresh: str = Field(..., min_length=20)


class UserResponse(BaseModel):
    id: str
    phone: str
    national_id: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    permissions: list[str] = []
    is_phone_verified: bool = False
    is_national_id_verified: bool = False
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access: str
    refresh: str
    user: UserResponse
