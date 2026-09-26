"""M31 — Academic QA API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import AcademicQANotFound
from app.db.models.academic_qa import (
    AcademicQAFinding,
    AcademicQARun,
)
from app.db.models.user import User
from app.db.session import get_db
from app.domain.academic_qa import QAStatus
from app.schemas.academic_qa import (
    AcademicQACurrentRead,
    AcademicQAFindingListResponse,
    AcademicQAFindingRead,
    AcademicQAGenerateRequest,
    AcademicQAGenerateResponse,
    AcademicQARunListResponse,
    AcademicQARunRead,
    AcademicQAValidationRead,
)
from app.services.academic_qa import jobs as qa_jobs
from app.services.academic_qa import persistence as qa_persist
from app.services.reports import get_report

router = APIRouter(prefix="/reports", tags=["academic-qa"])


def _load_current_run(
    db: Session, *, report_id: uuid.UUID,
) -> AcademicQARun:
    run = db.execute(
        select(AcademicQARun)
        .where(
            AcademicQARun.report_id == report_id,
            AcademicQARun.status == QAStatus.COMPLETED.value,
        )
        .order_by(
            AcademicQARun.created_at.desc(),
            AcademicQARun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise AcademicQANotFound()
    return run


@router.post(
    "/{report_id}/academic-qa/generate",
    response_model=AcademicQAGenerateResponse,
)
def generate_academic_qa(
    report_id: uuid.UUID,
    body: AcademicQAGenerateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcademicQAGenerateResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    settings = get_settings()

    effective_async = bool(body.async_)
    if effective_async and not settings.academic_qa_async_jobs:
        effective_async = False

    if effective_async:
        job_id = qa_jobs.enqueue_academic_qa(
            db,
            report_id=report_id,
            manuscript_version_id=body.manuscript_version_id,
            user_id=current_user.id,
            force=body.force,
        )
        response.status_code = 202
        return AcademicQAGenerateResponse(
            status="queued", job_id=job_id,
        )

    persisted = qa_persist.run_m31_persisted(
        db,
        report_id=report_id,
        manuscript_version_id=body.manuscript_version_id,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    return AcademicQAGenerateResponse(
        status=persisted.run.status,
        run_id=persisted.run.id,
        context_hash=persisted.run.context_hash,
        gate=persisted.run.gate,
        finding_count=persisted.run.finding_count,
        blocking_count=persisted.run.blocking_count,
    )


@router.get(
    "/{report_id}/academic-qa/current",
    response_model=AcademicQACurrentRead,
)
def get_current_academic_qa(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcademicQACurrentRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    return AcademicQACurrentRead(
        run=AcademicQARunRead.model_validate(run),
    )


@router.get(
    "/{report_id}/academic-qa/runs",
    response_model=AcademicQARunListResponse,
)
def list_academic_qa_runs(
    report_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcademicQARunListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    base = select(AcademicQARun).where(
        AcademicQARun.report_id == report_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            AcademicQARun.created_at.desc(),
            AcademicQARun.id.desc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return AcademicQARunListResponse(
        items=[AcademicQARunRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/{report_id}/academic-qa/runs/{run_id}",
    response_model=AcademicQARunRead,
)
def get_academic_qa_run(
    report_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcademicQARunRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = db.execute(
        select(AcademicQARun).where(
            AcademicQARun.id == run_id,
            AcademicQARun.report_id == report_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise AcademicQANotFound()
    return AcademicQARunRead.model_validate(run)


@router.get(
    "/{report_id}/academic-qa/findings",
    response_model=AcademicQAFindingListResponse,
)
def list_academic_qa_findings(
    report_id: uuid.UUID,
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcademicQAFindingListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    base = select(AcademicQAFinding).where(
        AcademicQAFinding.qa_run_id == run.id
    )
    if category:
        base = base.where(AcademicQAFinding.category == category)
    if severity:
        base = base.where(AcademicQAFinding.severity == severity)
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(AcademicQAFinding.created_at.asc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return AcademicQAFindingListResponse(
        items=[
            AcademicQAFindingRead.model_validate(r) for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/{report_id}/academic-qa/validate",
    response_model=AcademicQAValidationRead,
)
def validate_academic_qa(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcademicQAValidationRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    errors: list[str] = []
    warnings: list[str] = []

    if not run.context_hash:
        errors.append("missing_context_hash")

    findings = list(db.execute(
        select(AcademicQAFinding).where(
            AcademicQAFinding.qa_run_id == run.id
        )
    ).scalars().all())
    for f in findings:
        if not f.rule_id:
            errors.append(f"finding_missing_rule_id:{f.id}")

    if run.warnings:
        warnings.extend(str(w) for w in run.warnings)

    return AcademicQAValidationRead(
        validation_status="valid" if not errors else "invalid",
        validation_errors=errors,
        warnings=warnings,
        gate=run.gate,
    )
