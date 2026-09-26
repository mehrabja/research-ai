"""Notification and notification-preference service."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.notification import Notification, NotificationPreference


def get_preferences(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> NotificationPreference:
    row = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id
        )
    ).scalar_one_or_none()
    if row is None:
        row = NotificationPreference(user_id=user_id)
        db.add(row)
        db.flush()
    return row


def update_preferences(
    db: Session,
    *,
    user_id: uuid.UUID,
    values: dict[str, bool | None],
) -> NotificationPreference:
    row = get_preferences(db, user_id=user_id)
    for name, value in values.items():
        if value is not None and hasattr(row, name):
            setattr(row, name, value)
    db.commit()
    db.refresh(row)
    return row


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
    notification_type: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> Notification:
    row = Notification(
        user_id=user_id,
        workspace_id=workspace_id,
        notification_type=notification_type,
        title=title[:200],
        body=body[:4000],
        data=data,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_notifications(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
    limit: int,
) -> tuple[list[Notification], int]:
    limit = max(1, min(limit, 100))

    query = select(Notification).where(
        Notification.user_id == user_id
    )
    unread_query = select(func.count()).select_from(
        Notification
    ).where(
        Notification.user_id == user_id,
        Notification.read_at.is_(None),
    )

    if workspace_id is not None:
        query = query.where(
            Notification.workspace_id == workspace_id
        )
        unread_query = unread_query.where(
            Notification.workspace_id == workspace_id
        )

    rows = list(
        db.execute(
            query.order_by(
                Notification.created_at.desc()
            ).limit(limit)
        ).scalars().all()
    )
    unread = int(db.execute(unread_query).scalar_one())
    return rows, unread


def mark_read(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> Notification:
    row = db.execute(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("notification not found")

    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)

    return row
