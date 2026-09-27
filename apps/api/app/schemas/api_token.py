from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class APITokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    expires_at: datetime | None = None


class APITokenCreated(BaseModel):
    id: uuid.UUID
    name: str
    token: str
    token_prefix: str
    expires_at: datetime | None


class APITokenRead(BaseModel):
    id: uuid.UUID
    name: str
    token_prefix: str
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
