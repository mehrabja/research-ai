from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID | None
    kind: str
    title: str
    body: str
    data: dict[str, Any] | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int
    unread: int


class NotificationPreferenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferences: dict[str, bool]


class NotificationPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferences: dict[str, bool] = Field(default_factory=dict)
