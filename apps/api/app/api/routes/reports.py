"""Report CRUD routes.

POST   /api/v1/reports
GET    /api/v1/reports
GET    /api/v1/reports/{report_id}
PATCH  /api/v1/reports/{report_id}
PATCH  /api/v1/reports/{report_id}/status
DELETE /api/v1/reports/{report_id}
GET    /api/v1/reports/{report_id}/versions/{version_id}
POST   /api/v1/reports/{report_id}/versions
GET    /api/v1/reports/{report_id}/events

Every endpoint requires a valid Bearer JWT and is restricted to the
authenticated user's ownership scope.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.pipeline import GenerationRun
from app.db.models.report import Report, ReportEvent, ReportVersion
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.report_events import ReportEventResponse
from app.schemas.report_status import ReportStatusUpdate
from app.schemas.report_versions import (
    ReportVersionCreate,
    ReportVersionResponse,
)
from app.schemas.reports import (
    GenerationCurrentRead,
    ReportCreate,
    ReportResponse,
    ReportUpdate,
)
from app.services import report_events as report_events_service
from app.services import report_status as report_status_service
from app.services import report_versions as report_versions_service
from app.services import reports as reports_service

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new report",
)
def create_report(
    payload: ReportCreate,
    workspace_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    return reports_service.create_report(
        db,
        user_id=current_user.id,
        data=payload.model_dump(),
        workspace_id=workspace_id,
    )


@router.get(
    "",
    response_model=list[ReportResponse],
    summary="List the current user's active reports",
)
def list_reports(
    workspace_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Report]:
    return reports_service.list_reports(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
    )


@router.get(
    "/{report_id}/generation/current",
    response_model=GenerationCurrentRead,
    summary="Get current persisted generation output",
)
def get_current_generation(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerationCurrentRead:
    report = reports_service.get_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
    )
    run = db.execute(
        select(GenerationRun)
        .where(GenerationRun.report_id == report.id)
        .order_by(GenerationRun.created_at.desc(), GenerationRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        return GenerationCurrentRead(report_id=report_id)
    output = dict(run.output_json or {})
    return GenerationCurrentRead(
        report_id=report_id,
        run_id=run.id,
        status=run.status,
        prompt_version=run.prompt_version,
        provider=run.model_provider,
        model=run.model_version,
        input_tokens=run.input_token_count,
        output_tokens=run.output_token_count,
        language=output.get("language"),
        text=output.get("text"),
        context_hash=output.get("context_hash"),
        evidence=output.get("evidence") or [],
        cited_markers=output.get("cited_markers") or [],
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get a report by id",
)
def get_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    return reports_service.get_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
    )


@router.patch(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Partially update a report",
)
def update_report(
    report_id: uuid.UUID,
    payload: ReportUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    changes = payload.model_dump(exclude_unset=True)

    return reports_service.update_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
        changes=changes,
    )


@router.patch(
    "/{report_id}/status",
    response_model=ReportResponse,
    summary="Update report status",
)
def change_report_status(
    report_id: uuid.UUID,
    payload: ReportStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    return report_status_service.update_report_status(
        db,
        user_id=current_user.id,
        report_id=report_id,
        new_status=payload.status,
    )


@router.post(
    "/{report_id}/versions",
    response_model=ReportVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create report version",
)
def create_report_version(
    report_id: uuid.UUID,
    payload: ReportVersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportVersion:
    return report_versions_service.create_report_version(
        db,
        user_id=current_user.id,
        report_id=report_id,
        language=payload.language,
        content=payload.content,
    )


@router.get(
    "/{report_id}/versions/{version_id}",
    response_model=ReportVersionResponse,
    summary="Get report version",
)
def get_report_version(
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportVersion:
    return report_versions_service.get_report_version(
        db,
        user_id=current_user.id,
        report_id=report_id,
        version_id=version_id,
    )


@router.get(
    "/{report_id}/events",
    response_model=list[ReportEventResponse],
    summary="List audit events for a report",
)
def list_report_events(
    report_id: uuid.UUID,
    limit: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReportEvent]:
    return report_events_service.list_report_events(
        db,
        user_id=current_user.id,
        report_id=report_id,
        limit=limit,
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a report",
)
def delete_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    reports_service.soft_delete_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
    )
