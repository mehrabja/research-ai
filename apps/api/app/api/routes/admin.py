"""Protected platform administration routes."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import require_platform_admin
from app.core.exceptions import WorkspaceNotFound
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import get_db
from app.domain.workspace import WORKSPACE_STATUS_ACTIVE, WORKSPACE_STATUS_SUSPENDED
from app.schemas.workspace import WorkspaceRead
from app.services.workspaces import set_workspace_status

router=APIRouter(prefix="/admin",tags=["admin"])

@router.patch("/workspaces/{workspace_id}/status",response_model=WorkspaceRead)
def set_status(
    workspace_id:uuid.UUID,
    status_value:str=Query(..., pattern="^(active|suspended)$"),
    admin:User=Depends(require_platform_admin),
    db:Session=Depends(get_db),
)->WorkspaceRead:
    row=db.get(Workspace,workspace_id)
    if row is None:
        raise WorkspaceNotFound()
    if status_value not in (WORKSPACE_STATUS_ACTIVE,WORKSPACE_STATUS_SUSPENDED):
        from app.core.exceptions import AppError
        raise AppError("Unsupported workspace status.",code="WORKSPACE_STATUS_INVALID",status_code=422)
    row=set_workspace_status(db,workspace_id=workspace_id,status=status_value)
    db.commit();db.refresh(row)
    return WorkspaceRead.model_validate(row)

@router.get("/workspaces/{workspace_id}/subscription")
def subscription(
    workspace_id:uuid.UUID,
    admin:User=Depends(require_platform_admin),
    db:Session=Depends(get_db),
):
    row=db.execute(select(Subscription).where(Subscription.workspace_id==workspace_id).order_by(Subscription.created_at.desc()).limit(1)).scalar_one_or_none()
    if row is None: raise WorkspaceNotFound()
    return {"id":str(row.id),"workspace_id":str(row.workspace_id),"plan_id":str(row.plan_id),"status":row.status,"provider":row.provider,"provider_customer_id":row.provider_customer_id,"provider_subscription_id":row.provider_subscription_id}
