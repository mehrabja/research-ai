"""In-app notification routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationRead,
)
from app.services import notifications as notifications_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_user_notifications(
    workspace_id: uuid.UUID | None = Query(default=None),
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    rows, unread = notifications_service.list_notifications(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    total_rows, total_all = notifications_service.list_notifications(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        unread_only=False,
        limit=1,
        offset=0,
    )
    _ = total_rows
    return NotificationListResponse(
        items=[NotificationRead.model_validate(r) for r in rows],
        total=total_all,
        unread=unread,
    )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def read_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    notifications_service.mark_read(
        db,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    db.commit()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all_notifications(
    workspace_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    notifications_service.mark_all_read(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
    )
    db.commit()


@router.get("/preferences", response_model=NotificationPreferenceRead)
def get_preferences(
    workspace_id: uuid.UUID | None = None,
    channel: str = "in_app",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferenceRead:
    row = notifications_service.get_or_create_preferences(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        channel=channel,
    )
    db.commit()
    db.refresh(row)
    return NotificationPreferenceRead.model_validate(row)


@router.put("/preferences", response_model=NotificationPreferenceRead)
def update_preferences(
    payload: NotificationPreferenceUpdate,
    workspace_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferenceRead:
    row = notifications_service.get_or_create_preferences(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        channel=payload.channel,
    )
    row.preferences = payload.preferences
    db.commit()
    db.refresh(row)
    return NotificationPreferenceRead.model_validate(row)
