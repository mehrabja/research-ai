"""Notification persistence and read-state helpers."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.notifications import Notification, NotificationPreference

def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_type: str,
    title: str,
    body: str | None = None,
    workspace_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
) -> Notification:
    row = Notification(
        user_id=user_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(row)
    db.flush()
    return row

def list_notifications(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Notification], int]:
    conditions = [Notification.user_id == user_id]
    if workspace_id is not None:
        conditions.append(Notification.workspace_id == workspace_id)
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    rows = list(
        db.execute(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()
    )
    count = int(
        db.execute(
            select(func.count(Notification.id)).where(*conditions)
        ).scalar_one()
    )
    return rows, count

def mark_read(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> bool:
    row = db.execute(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        return False
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
    return True

def mark_all_read(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
) -> int:
    conditions = [
        Notification.user_id == user_id,
        Notification.read_at.is_(None),
    ]
    if workspace_id is not None:
        conditions.append(Notification.workspace_id == workspace_id)
    rows = db.execute(select(Notification).where(*conditions)).scalars().all()
    now = datetime.now(UTC)
    for row in rows:
        row.read_at = now
    return len(rows)

def get_or_create_preferences(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
    channel: str,
) -> NotificationPreference:
    row = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.workspace_id == workspace_id,
            NotificationPreference.channel == channel,
        )
    ).scalar_one_or_none()
    if row is None:
        row = NotificationPreference(
            user_id=user_id,
            workspace_id=workspace_id,
            channel=channel,
            preferences={
                "job": True,
                "review": True,
                "workspace": True,
                "billing": True,
                "security": True,
            },
        )
        db.add(row)
        db.flush()
    return row
