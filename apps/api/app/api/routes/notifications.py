"""M39 user notifications."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.notifications import NotificationListResponse, NotificationPreferencesRead, NotificationPreferencesUpdate, NotificationRead
from app.services import notifications as svc
router=APIRouter(prefix="/notifications",tags=["notifications"])
@router.get("",response_model=NotificationListResponse)
def list_notifications(workspace_id:uuid.UUID|None=None,limit:int=50,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->NotificationListResponse:
    rows,unread=svc.list_notifications(db,user_id=current_user.id,workspace_id=workspace_id,limit=limit)
    return NotificationListResponse(items=[NotificationRead.model_validate(x) for x in rows],total=len(rows),unread=unread)
@router.post("/{notification_id}/read",response_model=NotificationRead)
def read(notification_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->NotificationRead:
    return NotificationRead.model_validate(svc.mark_read(db,user_id=current_user.id,notification_id=notification_id))
@router.get("/preferences",response_model=NotificationPreferencesRead)
def preferences(current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->NotificationPreferencesRead:
    return NotificationPreferencesRead.model_validate(svc.get_preferences(db,user_id=current_user.id))
@router.patch("/preferences",response_model=NotificationPreferencesRead)
def update_preferences(body:NotificationPreferencesUpdate,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->NotificationPreferencesRead:
    return NotificationPreferencesRead.model_validate(svc.update_preferences(db,user_id=current_user.id,values=body.model_dump(exclude_unset=True)))
