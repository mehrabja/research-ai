"""API token schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class APITokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list, max_length=50)
    expires_days: int | None = Field(default=None, ge=1, le=3650)


class APITokenRead(BaseModel):
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
