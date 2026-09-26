"""Notification service."""
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.db.models.notification import Notification, NotificationPreference

def get_preferences(db: Session, *, user_id: uuid.UUID) -> NotificationPreference:
    row = db.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id)).scalar_one_or_none()
    if row is None:
        row = NotificationPreference(user_id=user_id)
        db.add(row)
        db.flush()
    return row

def update_preferences(db: Session, *, user_id: uuid.UUID, values: dict) -> NotificationPreference:
    row = get_preferences(db, user_id=user_id)
    for key, value in values.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, bool(value))
    db.commit()
    db.refresh(row)
    return row

def create_notification(db: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID | None, notification_type: str, title: str, body: str, data: dict | None = None) -> Notification:
    row = Notification(user_id=user_id, workspace_id=workspace_id, notification_type=notification_type, title=title[:200], body=body[:4000], data=data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def list_notifications(db: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID | None, limit: int = 50) -> tuple[list[Notification], int]:
    q = select(Notification).where(Notification.user_id == user_id)
    if workspace_id is not None:
        q = q.where(Notification.workspace_id == workspace_id)
    rows = list(db.execute(q.order_by(Notification.created_at.desc()).limit(max(1, min(limit, 100)))).scalars().all())
    count_q = select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    if workspace_id is not None:
        count_q = count_q.where(Notification.workspace_id == workspace_id)
    unread = int(db.execute(count_q).scalar_one())
    return rows, unread

def mark_read(db: Session, *, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    row = db.execute(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id).with_for_update()).scalar_one()
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return row
