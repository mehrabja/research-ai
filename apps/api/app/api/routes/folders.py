from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.folder import FolderCreate, FolderListResponse, FolderRead, FolderUpdate
from app.services import folders as folder_service

router = APIRouter(prefix="/projects", tags=["folders"])


@router.get("/{project_id}/folders", response_model=FolderListResponse)
def list_project_folders(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FolderListResponse:
    rows = folder_service.list_folders(db, project_id=project_id, user_id=current_user.id)
    return FolderListResponse(items=[FolderRead.model_validate(r, from_attributes=True) for r in rows], total=len(rows))


@router.post("/{project_id}/folders", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_project_folder(
    project_id: uuid.UUID,
    body: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FolderRead:
    row = folder_service.create_folder(
        db, project_id=project_id, user_id=current_user.id,
        name=body.name, parent_id=body.parent_id,
    )
    db.commit()
    db.refresh(row)
    return FolderRead.model_validate(row, from_attributes=True)


@router.patch("/{project_id}/folders/{folder_id}", response_model=FolderRead)
def update_project_folder(
    project_id: uuid.UUID,
    folder_id: uuid.UUID,
    body: FolderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FolderRead:
    row = folder_service.update_folder(
        db, project_id=project_id, user_id=current_user.id,
        folder_id=folder_id,
        name=body.name,
        parent_id=body.parent_id,
    )
    db.commit()
    db.refresh(row)
    return FolderRead.model_validate(row, from_attributes=True)
