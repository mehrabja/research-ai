"""M18-A — Project routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.project import (
    ProjectCreate,
    ProjectListItem,
    ProjectListResponse,
    ProjectRead,
    ProjectReportListItem,
    ProjectReportListResponse,
    ProjectUpdate,
)
from app.services import projects as projects_service

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_read(db: Session, *, user_id: uuid.UUID, project) -> ProjectRead:
    payload = projects_service.build_project_payload(
        db, user_id=user_id, project=project
    )
    return ProjectRead(**payload)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead:
    project = projects_service.create_project(
        db,
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        domain=body.domain,
        research_objective=body.research_objective,
        research_questions=body.research_questions,
        hypotheses=body.hypotheses,
        scope=body.scope,
        constraints=body.constraints,
        status=body.status,
    )
    return _to_read(db, user_id=current_user.id, project=project)


@router.get("", response_model=ProjectListResponse)
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    include_archived: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ProjectListResponse:
    rows, total = projects_service.list_projects(
        db,
        user_id=current_user.id,
        status=status_filter,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    items = [
        ProjectListItem(
            id=p.id,
            name=p.name,
            domain=p.domain,
            status=p.status,  # type: ignore[arg-type]
            report_count=count,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p, count in rows
    ]
    return ProjectListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead:
    project = projects_service.get_project(
        db, user_id=current_user.id, project_id=project_id
    )
    return _to_read(db, user_id=current_user.id, project=project)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead:
    # exclude_unset distinguishes omitted from explicit null.
    updates = body.model_dump(exclude_unset=True)
    project = projects_service.update_project(
        db,
        user_id=current_user.id,
        project_id=project_id,
        updates=updates,
    )
    return _to_read(db, user_id=current_user.id, project=project)


@router.post("/{project_id}/archive", response_model=ProjectRead)
def archive_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead:
    project = projects_service.archive_project(
        db, user_id=current_user.id, project_id=project_id
    )
    return _to_read(db, user_id=current_user.id, project=project)


@router.get("/{project_id}/reports", response_model=ProjectReportListResponse)
def list_project_reports(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ProjectReportListResponse:
    rows, total = projects_service.list_project_reports(
        db,
        user_id=current_user.id,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )
    items = [
        ProjectReportListItem(
            id=r.id,
            topic=r.topic,
            status=r.status,
            output_language=r.output_language,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return ProjectReportListResponse(
        items=items, total=total, limit=limit, offset=offset
    )
