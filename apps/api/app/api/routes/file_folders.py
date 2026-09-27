"""Project file folder routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.file_folder import (
    FileFolderCreate,
    FileFolderRead,
    FileFolderUpdate,
)
from app.services import file_folders as file_folders_service

router = APIRouter(prefix="/projects", tags=["file-folders"])


@router.get("/{project_id}/file-folders", response_model=list[FileFolderRead])
def list_project_folders(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FileFolderRead]:
    rows = file_folders_service.list_folders(
        db,
        project_id=project_id,
        user_id=current_user.id,
    )
    return [FileFolderRead.model_validate(r) for r in rows]


@router.post(
    "/{project_id}/file-folders",
    response_model=FileFolderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_folder(
    project_id: uuid.UUID,
    payload: FileFolderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileFolderRead:
    row = file_folders_service.create_folder(
        db,
        project_id=project_id,
        user_id=current_user.id,
        name=payload.name,
        parent_id=payload.parent_id,
    )
    return FileFolderRead.model_validate(row)


@router.patch(
    "/{project_id}/file-folders/{folder_id}",
    response_model=FileFolderRead,
)
def update_project_folder(
    project_id: uuid.UUID,
    folder_id: uuid.UUID,
    payload: FileFolderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileFolderRead:
    row = file_folders_service.update_folder(
        db,
        project_id=project_id,
        user_id=current_user.id,
        folder_id=folder_id,
        name=payload.name,
        parent_id=payload.parent_id,
    )
    return FileFolderRead.model_validate(row)


@router.delete(
    "/{project_id}/file-folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project_folder(
    project_id: uuid.UUID,
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    file_folders_service.delete_folder(
        db,
        project_id=project_id,
        user_id=current_user.id,
        folder_id=folder_id,
    )
