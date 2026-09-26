"""Notification API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID | None
    notification_type: str
    title: str
    body: str
    data: dict[str, Any] | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int
    unread: int


class NotificationPreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email_enabled: bool
    job_failures: bool
    review_assignments: bool
    usage_thresholds: bool
    weekly_digest: bool


class NotificationPreferencesUpdate(BaseModel):
    email_enabled: bool | None = None
    job_failures: bool | None = None
    review_assignments: bool | None = None
    usage_thresholds: bool | None = None
    weekly_digest: bool | None = None
