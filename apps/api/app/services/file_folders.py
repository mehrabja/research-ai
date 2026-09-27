"""Project file folder lifecycle service."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ProjectNotFound
from app.db.models.file_folder import ProjectFileFolder
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile

class FileFolderError(Exception): ...

def _require_project(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Project:
    project = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFound()
    return project

def _validate_parent(
    db: Session,
    *,
    project_id: uuid.UUID,
    parent_id: uuid.UUID | None,
) -> None:
    if parent_id is None:
        return
    parent = db.execute(
        select(ProjectFileFolder).where(
            ProjectFileFolder.id == parent_id,
            ProjectFileFolder.project_id == project_id,
        )
    ).scalar_one_or_none()
    if parent is None:
        raise FileFolderError("parent folder does not belong to project")

def list_folders(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[ProjectFileFolder]:
    _require_project(db, project_id=project_id, user_id=user_id)
    return list(
        db.execute(
            select(ProjectFileFolder)
            .where(ProjectFileFolder.project_id == project_id)
            .order_by(ProjectFileFolder.name.asc(), ProjectFileFolder.created_at.asc())
        ).scalars().all()
    )

def create_folder(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None,
) -> ProjectFileFolder:
    _require_project(db, project_id=project_id, user_id=user_id)
    _validate_parent(db, project_id=project_id, parent_id=parent_id)
    row = ProjectFileFolder(
        project_id=project_id,
        parent_id=parent_id,
        name=name.strip(),
        created_by=user_id,
    )
    if not row.name:
        raise FileFolderError("folder name is empty")
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except IntegrityError as exc:
        db.rollback()
        raise FileFolderError("a folder with that name already exists") from exc
    return row

def update_folder(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    folder_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None,
) -> ProjectFileFolder:
    _require_project(db, project_id=project_id, user_id=user_id)
    row = db.execute(
        select(ProjectFileFolder)
        .where(
            ProjectFileFolder.id == folder_id,
            ProjectFileFolder.project_id == project_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise FileFolderError("folder not found")
    _validate_parent(db, project_id=project_id, parent_id=parent_id)
    if parent_id == row.id:
        raise FileFolderError("folder cannot be its own parent")
    row.name = name.strip()
    if not row.name:
        raise FileFolderError("folder name is empty")
    row.parent_id = parent_id
    try:
        db.commit()
        db.refresh(row)
    except IntegrityError as exc:
        db.rollback()
        raise FileFolderError("a folder with that name already exists") from exc
    return row

def delete_folder(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    folder_id: uuid.UUID,
) -> None:
    _require_project(db, project_id=project_id, user_id=user_id)
    row = db.execute(
        select(ProjectFileFolder)
        .where(
            ProjectFileFolder.id == folder_id,
            ProjectFileFolder.project_id == project_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise FileFolderError("folder not found")
    child_count = int(
        db.execute(
            select(func.count(ProjectFileFolder.id)).where(
                ProjectFileFolder.project_id == project_id,
                ProjectFileFolder.parent_id == folder_id,
            )
        ).scalar_one()
    )
    file_count = int(
        db.execute(
            select(func.count(ProjectFile.id)).where(
                ProjectFile.project_id == project_id,
                ProjectFile.folder_id == folder_id,
                ProjectFile.deleted_at.is_(None),
            )
        ).scalar_one()
    )
    if child_count or file_count:
        raise FileFolderError("folder must be empty before deletion")
    db.delete(row)
    db.commit()

def validate_folder_for_file(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    folder_id: uuid.UUID | None,
) -> None:
    _require_project(db, project_id=project_id, user_id=user_id)
    _validate_parent(db, project_id=project_id, parent_id=folder_id)
