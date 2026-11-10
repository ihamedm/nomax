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


class PasswordLogin(BaseModel):
    phone: str = Field(..., min_length=8, max_length=13)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=13)
    full_name: str = Field(..., min_length=3, max_length=120)
    national_id: str = Field(..., min_length=10, max_length=10)
    # Length is enforced in the service so a too-short password returns the
    # specific `password_too_short` code instead of a generic validation error.
    password: str = Field(..., max_length=128)


class ForgotPasswordRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=13)


class ResetPasswordRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=13)
    code: str = Field(..., min_length=6, max_length=6)
    # The OTP is checked before password length, so keep length in the service.
    password: str = Field(..., max_length=128)


class UserResponse(BaseModel):
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


class TokenResponse(BaseModel):
    access: str
    refresh: str
    user: UserResponse
