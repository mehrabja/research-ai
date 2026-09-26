from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    settings: dict[str, Any] | None = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    owner_user_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime


class WorkspaceListItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    role: str


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceListItem]
    total: int
