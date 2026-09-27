from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models.notification import Notification
from app.db.models.notification_preference import NotificationPreference


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    body: str,
    workspace_id: uuid.UUID | None = None,
    data: dict | None = None,
) -> Notification:
    row = Notification(
        user_id=user_id,
        workspace_id=workspace_id,
        kind=kind,
        title=title,
        body=body,
        data=data,
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
) -> tuple[list[Notification], int, int]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    count_stmt = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id
    )

    if workspace_id is not None:
        stmt = stmt.where(Notification.workspace_id == workspace_id)
        count_stmt = count_stmt.where(Notification.workspace_id == workspace_id)

    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
        count_stmt = count_stmt.where(Notification.read_at.is_(None))

    rows = list(
        db.execute(
            stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )
    total = int(db.execute(count_stmt).scalar_one())

    unread_stmt = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id,
        Notification.read_at.is_(None),
    )
    if workspace_id is not None:
        unread_stmt = unread_stmt.where(
            Notification.workspace_id == workspace_id
        )
    unread = int(db.execute(unread_stmt).scalar_one())
    return rows, total, unread


def mark_read(
    db: Session,
    *,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Notification | None:
    row = db.execute(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.flush()
    return row


def mark_all_read(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
) -> int:
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    )
    if workspace_id is not None:
        stmt = stmt.where(Notification.workspace_id == workspace_id)
    result = db.execute(
        stmt.values(read_at=datetime.now(UTC))
    )
    db.flush()
    return int(result.rowcount or 0)


def get_preferences(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> dict[str, bool]:
    row = db.get(NotificationPreference, user_id)
    if row is None:
        return {}
    return {str(key): bool(value) for key, value in (row.preferences or {}).items()}


def update_preferences(
    db: Session,
    *,
    user_id: uuid.UUID,
    preferences: dict[str, bool],
) -> dict[str, bool]:
    row = db.get(NotificationPreference, user_id)
    if row is None:
        row = NotificationPreference(
            user_id=user_id,
            preferences=dict(preferences),
        )
        db.add(row)
    else:
        row.preferences = {
            **(row.preferences or {}),
            **preferences,
        }
    db.flush()
    return get_preferences(db, user_id=user_id)
