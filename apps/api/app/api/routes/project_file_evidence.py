from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.evidence import (
    CanonicalProjectEvidenceKind,
    EvidenceListResponse,
)
from app.schemas.project_file_evidence import (
    ProjectFileEvidenceListResponse,
    ProjectFileEvidenceRead,
    ProjectFileEvidenceSyncRequest,
    ProjectFileEvidenceSyncResponse,
)
from app.services import project_file_evidence as evidence_service
from app.services.artifact_evidence import sync_ready_project_files_for_report
from app.services.projects import get_project
from app.services.reports import list_reports

router = APIRouter(prefix="/projects", tags=["file-evidence"])


@router.get(
    "/{project_id}/evidence",
    response_model=EvidenceListResponse,
)
def list_canonical_evidence(
    project_id: uuid.UUID,
    kind: CanonicalProjectEvidenceKind | None = Query(default=None),
    file_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceListResponse:
    items, total = evidence_service.list_canonical_project_evidence(
        db,
        user_id=current_user.id,
        project_id=project_id,
        kind=kind,
        file_id=file_id,
        limit=limit,
        offset=offset,
    )
    return EvidenceListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{project_id}/evidence/files",
    response_model=ProjectFileEvidenceListResponse,
)
def list_file_evidence(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectFileEvidenceListResponse:
    items, total = evidence_service.list_project_file_evidence(
        db,
        user_id=current_user.id,
        project_id=project_id,
    )
    return ProjectFileEvidenceListResponse(
        items=[
            ProjectFileEvidenceRead.model_validate(item)
            for item in items
        ],
        total=total,
    )


@router.post(
    "/{project_id}/evidence/sync",
    response_model=ProjectFileEvidenceSyncResponse,
)
def sync_file_evidence(
    project_id: uuid.UUID,
    payload: ProjectFileEvidenceSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectFileEvidenceSyncResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)

    if payload.report_id is not None:
        synced = evidence_service.sync_project_file_evidence_for_report(
            db,
            user_id=current_user.id,
            project_id=project_id,
            report_id=payload.report_id,
        )
        return ProjectFileEvidenceSyncResponse(
            synced_reports=1,
            synced_files=synced,
        )

    reports = list_reports(
        db,
        user_id=current_user.id,
        workspace_id=None,
    )
    project_reports = [
        report for report in reports
        if report.project_id == project_id
    ]
    total_synced = 0
    for report in project_reports:
        total_synced += sync_ready_project_files_for_report(
            db,
            project_id=project_id,
            report_id=report.id,
            user_id=current_user.id,
        )
    return ProjectFileEvidenceSyncResponse(
        synced_reports=len(project_reports),
        synced_files=total_synced,
    )
