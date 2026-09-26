"""M29 — Technical Intelligence API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import TechnicalIntelligenceNotFound
from app.db.models.experiment_result import ExperimentResult
from app.db.models.metric import Metric
from app.db.models.technical_fact import TechnicalFact
from app.db.models.technical_intelligence import (
    TechnicalIntelligenceRun,
)
from app.db.models.user import User
from app.db.session import get_db
from app.domain.technical_intelligence import M29_VERSION
from app.schemas.technical_intelligence import (
    ExperimentResultListResponse,
    ExperimentResultRead,
    MetricListResponse,
    MetricRead,
    TechnicalFactListResponse,
    TechnicalFactRead,
    TechnicalIntelligenceCurrentRead,
    TechnicalIntelligenceGenerateRequest,
    TechnicalIntelligenceGenerateResponse,
    TechnicalIntelligenceRunListResponse,
    TechnicalIntelligenceRunRead,
    TechnicalIntelligenceValidationRead,
)
from app.services.projects import get_project
from app.services.technical_intelligence import jobs as jobs_svc
from app.services.technical_intelligence import persistence as persist_svc

router = APIRouter(prefix="/projects", tags=["technical-intelligence"])


def _load_current_run(
    db: Session, *, project_id: uuid.UUID,
) -> TechnicalIntelligenceRun:
    run = db.execute(
        select(TechnicalIntelligenceRun)
        .where(
            TechnicalIntelligenceRun.project_id == project_id,
            TechnicalIntelligenceRun.status == "completed",
        )
        .order_by(
            TechnicalIntelligenceRun.created_at.desc(),
            TechnicalIntelligenceRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise TechnicalIntelligenceNotFound()
    return run


@router.post(
    "/{project_id}/technical-intelligence/generate",
    response_model=TechnicalIntelligenceGenerateResponse,
)
def generate_technical_intelligence(
    project_id: uuid.UUID,
    body: TechnicalIntelligenceGenerateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TechnicalIntelligenceGenerateResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    settings = get_settings()

    effective_async = bool(body.async_)
    if effective_async and not getattr(
        settings, "technical_intelligence_async_jobs", False
    ):
        effective_async = False

    if effective_async:
        job_id = jobs_svc.enqueue_technical_intelligence(
            db,
            project_id=project_id,
            user_id=current_user.id,
            force=body.force,
        )
        response.status_code = 202
        return TechnicalIntelligenceGenerateResponse(
            status="queued", job_id=job_id,
        )

    persisted = persist_svc.run_m29_persisted(
        db,
        project_id=project_id,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    return TechnicalIntelligenceGenerateResponse(
        status=persisted.run.status,
        run_id=persisted.run.id,
        context_hash=persisted.run.context_hash,
        fact_count=persisted.run.fact_count,
        result_count=persisted.run.result_count,
        metric_count=persisted.run.metric_count,
    )


@router.get(
    "/{project_id}/technical-intelligence",
    response_model=TechnicalIntelligenceCurrentRead,
)
def get_current_technical_intelligence(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TechnicalIntelligenceCurrentRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    run = _load_current_run(db, project_id=project_id)
    return TechnicalIntelligenceCurrentRead(
        run=TechnicalIntelligenceRunRead.model_validate(run),
        fact_count=run.fact_count,
        result_count=run.result_count,
        metric_count=run.metric_count,
    )


@router.get(
    "/{project_id}/technical-intelligence/runs",
    response_model=TechnicalIntelligenceRunListResponse,
)
def list_technical_intelligence_runs(
    project_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TechnicalIntelligenceRunListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    base = select(TechnicalIntelligenceRun).where(
        TechnicalIntelligenceRun.project_id == project_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            TechnicalIntelligenceRun.created_at.desc(),
            TechnicalIntelligenceRun.id.desc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return TechnicalIntelligenceRunListResponse(
        items=[
            TechnicalIntelligenceRunRead.model_validate(r) for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/{project_id}/technical-intelligence/facts",
    response_model=TechnicalFactListResponse,
)
def list_technical_facts(
    project_id: uuid.UUID,
    fact_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TechnicalFactListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    run = _load_current_run(db, project_id=project_id)
    base = select(TechnicalFact).where(
        TechnicalFact.technical_intelligence_run_id == run.id,
    )
    if fact_type:
        base = base.where(TechnicalFact.fact_type == fact_type)
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(TechnicalFact.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return TechnicalFactListResponse(
        items=[TechnicalFactRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/{project_id}/technical-intelligence/results",
    response_model=ExperimentResultListResponse,
)
def list_experiment_results(
    project_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExperimentResultListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    run = _load_current_run(db, project_id=project_id)
    base = select(ExperimentResult).where(
        ExperimentResult.technical_intelligence_run_id == run.id,
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(ExperimentResult.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return ExperimentResultListResponse(
        items=[
            ExperimentResultRead.model_validate(r) for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/{project_id}/technical-intelligence/metrics",
    response_model=MetricListResponse,
)
def list_metrics(
    project_id: uuid.UUID,
    normalized_name: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MetricListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    run = _load_current_run(db, project_id=project_id)
    base = select(Metric).where(
        Metric.technical_intelligence_run_id == run.id,
    )
    if normalized_name:
        base = base.where(
            Metric.normalized_name == normalized_name
        )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(Metric.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return MetricListResponse(
        items=[MetricRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/{project_id}/technical-intelligence/validate",
    response_model=TechnicalIntelligenceValidationRead,
)
def validate_technical_intelligence(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TechnicalIntelligenceValidationRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    run = _load_current_run(db, project_id=project_id)
    errors: list[str] = []
    warnings: list[str] = []

    if not run.context_hash:
        errors.append("missing_context_hash")
    if run.m29_version != M29_VERSION:
        errors.append("version_mismatch")

    facts = list(db.execute(
        select(TechnicalFact).where(
            TechnicalFact.technical_intelligence_run_id == run.id,
        )
    ).scalars().all())
    for f in facts:
        if not f.provenance:
            errors.append(f"fact_missing_provenance:{f.id}")

    metrics = list(db.execute(
        select(Metric).where(
            Metric.technical_intelligence_run_id == run.id,
        )
    ).scalars().all())
    for m in metrics:
        if not m.provenance:
            errors.append(f"metric_missing_provenance:{m.id}")

    return TechnicalIntelligenceValidationRead(
        validation_status="valid" if not errors else "invalid",
        validation_errors=errors,
        warnings=warnings,
    )
