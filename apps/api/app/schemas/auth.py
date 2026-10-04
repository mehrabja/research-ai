"""Authentication request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=15, max_length=256)
    full_name: str | None = Field(default=None, max_length=200)
    workspace_name: str | None = Field(default=None, min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=256)
    two_factor_code: str | None = Field(default=None, min_length=6, max_length=6)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    session_id: uuid.UUID | None = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None
    user_agent: str | None
    ip_address: str | None


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int


class EmailTokenRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=512)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=512)
    new_password: str = Field(..., min_length=15, max_length=256)


class MessageResponse(BaseModel):
    message: str


class TwoFactorEnrollmentResponse(BaseModel):
    enabled: bool
    secret: str
    provisioning_uri: str
    recovery_codes: list[str]


class TwoFactorStatusResponse(BaseModel):
    enabled: bool


class TwoFactorConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class APITokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list, max_length=50)
    expires_days: int | None = Field(default=None, ge=1, le=3650)


class APITokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    token_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class APITokenCreateResponse(BaseModel):
    token: str
    item: APITokenRead


class TwoFactorDisableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = None


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
