from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import NotificationNotFound
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationRead,
)
from app.services import notifications as notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _read(row) -> NotificationRead:
    return NotificationRead.model_validate(row, from_attributes=True)


@router.get("", response_model=NotificationListResponse)
def list_user_notifications(
    workspace_id: uuid.UUID | None = Query(default=None),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    rows, total, unread = notification_service.list_notifications(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(
        items=[_read(row) for row in rows],
        total=total,
        unread=unread,
    )


@router.post(
    "/{notification_id}/read",
    response_model=NotificationRead,
)
def read_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationRead:
    row = notification_service.mark_read(
        db,
        notification_id=notification_id,
        user_id=current_user.id,
    )
    if row is None:
        raise NotificationNotFound()
    db.commit()
    return _read(row)


@router.post(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
)
def read_all_notifications(
    workspace_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    notification_service.mark_all_read(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
    )
    db.commit()


@router.get("/preferences", response_model=NotificationPreferenceRead)
def read_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferenceRead:
    return NotificationPreferenceRead(
        preferences=notification_service.get_preferences(
            db,
            user_id=current_user.id,
        )
    )


@router.patch("/preferences", response_model=NotificationPreferenceRead)
def patch_preferences(
    body: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferenceRead:
    preferences = notification_service.update_preferences(
        db,
        user_id=current_user.id,
        preferences=body.preferences,
    )
    db.commit()
    return NotificationPreferenceRead(preferences=preferences)
