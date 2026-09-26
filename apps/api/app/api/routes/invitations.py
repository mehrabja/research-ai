"""M37 Phase 2-D — top-level invitation accept route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.invitation import InvitationAcceptResponse
from app.services import invitations as invitations_service

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post(
    "/{token}/accept",
    response_model=InvitationAcceptResponse,
)
def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationAcceptResponse:
    m = invitations_service.accept_invitation(
        db, raw_token=token, user_id=current_user.id
    )
    db.commit()
    db.refresh(m)
    return InvitationAcceptResponse(
        workspace_id=m.workspace_id,
        user_id=m.user_id,
        role=m.role,
        status=m.status,
    )
