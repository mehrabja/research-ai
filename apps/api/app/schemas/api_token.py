from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.security.api_scopes import DEFAULT_SCOPES, normalize_scopes


class APITokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=lambda: list(DEFAULT_SCOPES))
    allowed_workspace_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    allowed_project_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        try:
            return list(normalize_scopes(value))
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class APITokenCreated(BaseModel):
    id: uuid.UUID
    name: str
    token: str
    token_prefix: str
    expires_at: datetime | None
    scopes: list[str]
    allowed_workspace_ids: list[str]
    allowed_project_ids: list[str]


class APITokenRead(BaseModel):
    id: uuid.UUID
    name: str
    token_prefix: str
    scopes: list[str]
    allowed_workspace_ids: list[str]
    allowed_project_ids: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
