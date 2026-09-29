"""Authentication request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=15, max_length=256)
    full_name: str | None = Field(default=None, min_length=1, max_length=160)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=256)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=32, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=32, max_length=512)


class AccountDeleteRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=256)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=512)
    new_password: str = Field(..., min_length=15, max_length=256)


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=512)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


class SessionResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
