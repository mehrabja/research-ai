"""M32 — Manuscript humanization API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import ManuscriptHumanizationNotFound
from app.db.models.humanization import (
    HumanizationIteration,
    HumanizationRun,
)
from app.db.models.user import User
from app.db.session import get_db
from app.domain.humanization_m32 import (
    HUMANIZATION_MODES,
    M32_STAGE,
)
from app.schemas.manuscript_humanization import (
    HumanizationIterationListResponse,
    HumanizationIterationRead,
    HumanizationRunListResponse,
    HumanizationRunRead,
    ManuscriptHumanizationCurrentRead,
    ManuscriptHumanizationRequest,
    ManuscriptHumanizationResponse,
    ManuscriptHumanizationValidationRead,
)
from app.services.manuscript_humanization import jobs as jobs_svc
from app.services.manuscript_humanization import persistence as persist_svc
from app.services.reports import get_report

router = APIRouter(prefix="/reports", tags=["manuscript-humanization"])


def _load_current_run(
    db: Session, *, report_id: uuid.UUID,
) -> HumanizationRun:
    run = db.execute(
        select(HumanizationRun)
        .where(
            HumanizationRun.report_id == report_id,
            HumanizationRun.stage == M32_STAGE,
            HumanizationRun.status == "success",
        )
        .order_by(
            HumanizationRun.created_at.desc(),
            HumanizationRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise ManuscriptHumanizationNotFound()
    return run


@router.post(
    "/{report_id}/manuscript-humanization/generate",
    response_model=ManuscriptHumanizationResponse,
)
def generate_manuscript_humanization(
    report_id: uuid.UUID,
    body: ManuscriptHumanizationRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptHumanizationResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    settings = get_settings()

    if body.mode not in HUMANIZATION_MODES:
        response.status_code = 422
        return ManuscriptHumanizationResponse(status="invalid_mode")

    effective_async = bool(body.async_)
    if effective_async and not settings.manuscript_humanization_async_jobs:
        effective_async = False

    if effective_async:
        job_id = jobs_svc.enqueue_manuscript_humanization(
            db,
            report_id=report_id,
            manuscript_version_id=body.manuscript_version_id,
            user_id=current_user.id,
            mode=body.mode,
            force=body.force,
        )
        response.status_code = 202
        return ManuscriptHumanizationResponse(
            status="queued", job_id=job_id,
        )

    persisted = persist_svc.run_m32_persisted(
        db,
        report_id=report_id,
        manuscript_version_id=body.manuscript_version_id,
        mode=body.mode,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    return ManuscriptHumanizationResponse(
        status=persisted.run.status,
        run_id=persisted.run.id,
        context_hash=persisted.run.context_hash,
        gate=persisted.run.gate,
    )


@router.get(
    "/{report_id}/manuscript-humanization/current",
    response_model=ManuscriptHumanizationCurrentRead,
)
def get_current_manuscript_humanization(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptHumanizationCurrentRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    return ManuscriptHumanizationCurrentRead(
        run=HumanizationRunRead.model_validate(run),
    )


@router.get(
    "/{report_id}/manuscript-humanization/runs",
    response_model=HumanizationRunListResponse,
)
def list_manuscript_humanization_runs(
    report_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HumanizationRunListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    base = select(HumanizationRun).where(
        HumanizationRun.report_id == report_id,
        HumanizationRun.stage == M32_STAGE,
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            HumanizationRun.created_at.desc(),
            HumanizationRun.id.desc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return HumanizationRunListResponse(
        items=[HumanizationRunRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/{report_id}/manuscript-humanization/runs/{run_id}/iterations",
    response_model=HumanizationIterationListResponse,
)
def list_humanization_iterations(
    report_id: uuid.UUID,
    run_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HumanizationIterationListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = db.execute(
        select(HumanizationRun).where(
            HumanizationRun.id == run_id,
            HumanizationRun.report_id == report_id,
            HumanizationRun.stage == M32_STAGE,
        )
    ).scalar_one_or_none()
    if run is None:
        raise ManuscriptHumanizationNotFound()
    base = select(HumanizationIteration).where(
        HumanizationIteration.humanization_run_id == run_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(HumanizationIteration.iteration_index.asc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return HumanizationIterationListResponse(
        items=[
            HumanizationIterationRead.model_validate(r) for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/{report_id}/manuscript-humanization/validate",
    response_model=ManuscriptHumanizationValidationRead,
)
def validate_manuscript_humanization(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptHumanizationValidationRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    errors: list[str] = []
    warnings: list[str] = []

    if not run.context_hash:
        errors.append("missing_context_hash")
    if run.mode not in HUMANIZATION_MODES:
        errors.append("invalid_mode")

    warnings.extend(
        str(w) for w in (run.policy_json or {}).get("warnings", [])
    )

    return ManuscriptHumanizationValidationRead(
        validation_status="valid" if not errors else "invalid",
        validation_errors=errors,
        warnings=warnings,
        gate=run.gate,
    )
