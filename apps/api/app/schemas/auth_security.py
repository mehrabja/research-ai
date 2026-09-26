"""M39 auth/session/API token/2FA schemas."""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None
    user_agent: str | None

class SessionListResponse(BaseModel):
    items: list[SessionRead]
    total: int

class RefreshRequest(BaseModel):
    refresh_token: str | None = None
    csrf_token: str | None = None

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=15, max_length=256)

class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)

class ApiTokenCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    expires_at: datetime | None = None

class ApiTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    token_prefix: str
    label: str
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

class ApiTokenCreated(BaseModel):
    token: str
    token_info: ApiTokenRead

class TotpSetupResponse(BaseModel):
    secret: str
    issuer: str
    account_name: str
    otpauth_url: str

class TotpVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)

class TotpStatusResponse(BaseModel):
    enabled: bool
    recovery_codes_remaining: int


class OAuthStartResponse(BaseModel):
    provider: str
    authorization_url: str
