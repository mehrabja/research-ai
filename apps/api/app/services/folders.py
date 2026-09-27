from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ProjectNotFound
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.project_folder import ProjectFolder


def _require_project(db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFound()
    return project


def list_folders(db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID) -> list[ProjectFolder]:
    _require_project(db, project_id=project_id, user_id=user_id)
    return list(
        db.execute(
            select(ProjectFolder)
            .where(ProjectFolder.project_id == project_id)
            .order_by(ProjectFolder.parent_id.nullsfirst(), ProjectFolder.name.asc())
        ).scalars()
    )


def create_folder(db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID, name: str, parent_id: uuid.UUID | None) -> ProjectFolder:
    _require_project(db, project_id=project_id, user_id=user_id)
    if parent_id is not None:
        parent = db.execute(
            select(ProjectFolder).where(
                ProjectFolder.id == parent_id,
                ProjectFolder.project_id == project_id,
            )
        ).scalar_one_or_none()
        if parent is None:
            raise AppError("parent folder not found", code="FOLDER_NOT_FOUND")
    row = ProjectFolder(project_id=project_id, parent_id=parent_id, name=name.strip())
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("folder with this name already exists", code="FOLDER_CONFLICT",) from exc
    return row


def update_folder(db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID, folder_id: uuid.UUID, name: str | None, parent_id: uuid.UUID | None) -> ProjectFolder:
    _require_project(db, project_id=project_id, user_id=user_id)
    row = db.execute(
        select(ProjectFolder).where(ProjectFolder.id == folder_id, ProjectFolder.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        raise AppError("folder not found", code="FOLDER_NOT_FOUND")
    if parent_id == folder_id:
        raise AppError("folder cannot be its own parent", code="FOLDER_CYCLE")
    if parent_id is not None:
        parent = db.execute(
            select(ProjectFolder).where(ProjectFolder.id == parent_id, ProjectFolder.project_id == project_id)
        ).scalar_one_or_none()
        if parent is None:
            raise AppError("parent folder not found", code="FOLDER_NOT_FOUND")
        current = parent
        seen: set[uuid.UUID] = set()
        while current.parent_id is not None:
            if current.id in seen or current.parent_id == folder_id:
                raise AppError("folder move would create a cycle", code="FOLDER_CYCLE")
            seen.add(current.id)
            current = db.get(ProjectFolder, current.parent_id)
            if current is None:
                break
    if name is not None:
        row.name = name.strip()
    row.parent_id = parent_id
    db.flush()
    return row
