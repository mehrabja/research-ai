"""Notification API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    notification_type: str
    title: str
    body: str | None
    resource_type: str | None
    resource_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int
    unread: int


class NotificationPreferenceUpdate(BaseModel):
    channel: str = Field(default="in_app", min_length=2, max_length=32)
    preferences: dict[str, bool]


class NotificationPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID | None
    channel: str
    preferences: dict[str, bool]
    created_at: datetime
    updated_at: datetime
