from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.manuscript import ManuscriptVersionRead
from app.schemas.manuscript_draft import (
    ManuscriptDraftRead,
    ManuscriptDraftWriteRequest,
    ManuscriptDraftCommitRequest,
)
from app.services.manuscript_drafts import (
    autosave,
    commit_draft,
    discard,
    get_draft,
)
router = APIRouter(prefix="/reports", tags=["manuscript-drafts"])


@router.get("/{report_id}/manuscript/draft", response_model=ManuscriptDraftRead)
def read_draft(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptDraftRead:
    return ManuscriptDraftRead.model_validate(
        get_draft(db, report_id=report_id, user_id=current_user.id)
    )


@router.put("/{report_id}/manuscript/draft", response_model=ManuscriptDraftRead)
def save_draft(
    report_id: uuid.UUID,
    body: ManuscriptDraftWriteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptDraftRead:
    row = autosave(
        db,
        report_id=report_id,
        user_id=current_user.id,
        base_version_id=body.base_version_id,
        revision=body.revision,
        content=body.content,
    )
    db.commit()
    db.refresh(row)
    return ManuscriptDraftRead.model_validate(row)


@router.post(
    "/{report_id}/manuscript/draft/commit",
    response_model=ManuscriptVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def save_draft_as_version(
    report_id: uuid.UUID,
    body: ManuscriptDraftCommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = commit_draft(
        db,
        report_id=report_id,
        user_id=current_user.id,
        base_version_id=body.base_version_id,
        revision=body.revision,
    )
    db.commit()
    db.refresh(version)
    return version


@router.delete(
    "/{report_id}/manuscript/draft",
    status_code=status.HTTP_204_NO_CONTENT,
)
def discard_manuscript_draft(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    discard(
        db,
        report_id=report_id,
        user_id=current_user.id,
    )
    db.commit()
