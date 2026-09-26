"""M28 — Section Research API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import (
    SectionResearchNotFound,
)
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.section_research import (
    CoverageSummaryRead,
    EvidenceItemRead,
    SectionResearchCurrentRead,
    SectionResearchGenerateRequest,
    SectionResearchGenerateResponse,
    SectionResearchRunListResponse,
    SectionResearchRunRead,
    SectionResearchValidationRead,
)
from app.services import reports as reports_service
from app.services.section_research import jobs as jobs_svc
from app.services.section_research import persistence as persist_svc

router = APIRouter(prefix="/reports", tags=["section-research"])


def _load_chain(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    section_id: uuid.UUID,
) -> ManuscriptSection:
    reports_service.get_report(
        db, user_id=user_id, report_id=report_id
    )
    section = db.get(ManuscriptSection, section_id)
    if section is None:
        raise SectionResearchNotFound()
    version = db.get(ManuscriptVersion, section.manuscript_version_id)
    if version is None:
        raise SectionResearchNotFound()
    manuscript = db.get(Manuscript, version.manuscript_id)
    if manuscript is None or manuscript.report_id != report_id:
        raise SectionResearchNotFound()
    if manuscript.current_version_id != version.id:
        raise SectionResearchNotFound()
    return section


def _load_current_run(
    db: Session, *, section_id: uuid.UUID,
) -> SectionResearchRun:
    run = db.execute(
        select(SectionResearchRun)
        .where(
            SectionResearchRun.manuscript_section_id == section_id,
            SectionResearchRun.status == "completed",
        )
        .order_by(SectionResearchRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise SectionResearchNotFound()
    return run


@router.post(
    "/{report_id}/manuscript/sections/{section_id}/research",
    response_model=SectionResearchGenerateResponse,
)
def generate_section_research(
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    body: SectionResearchGenerateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectionResearchGenerateResponse:
    _load_chain(
        db, user_id=current_user.id,
        report_id=report_id, section_id=section_id,
    )
    settings = get_settings()

    effective_async = bool(body.async_)
    if effective_async and not getattr(
        settings, "section_research_async_jobs", False
    ):
        effective_async = False

    if effective_async:
        job_id = jobs_svc.enqueue_section_research(
            db,
            report_id=report_id,
            section_id=section_id,
            user_id=current_user.id,
            force=body.force,
        )
        response.status_code = 202
        return SectionResearchGenerateResponse(
            status="queued", job_id=job_id,
        )

    persisted = persist_svc.run_section_research_persisted(
        db,
        user_id=current_user.id,
        report_id=report_id,
        section_id=section_id,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    return SectionResearchGenerateResponse(
        status=persisted.run.status,
        run_id=persisted.run.id,
        context_hash=persisted.run.context_hash,
        contract_hash=persisted.run.contract_hash,
        evidence_count=persisted.run.selected_evidence_count,
        coverage_score=float(persisted.run.coverage_score),
        coverage_state=persisted.run.coverage_state,
    )


@router.get(
    "/{report_id}/manuscript/sections/{section_id}/research",
    response_model=SectionResearchCurrentRead,
)
def get_current_section_research(
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectionResearchCurrentRead:
    _load_chain(
        db, user_id=current_user.id,
        report_id=report_id, section_id=section_id,
    )
    run = _load_current_run(db, section_id=section_id)
    evidence = list(db.execute(
        select(SectionResearchEvidence)
        .where(SectionResearchEvidence.research_run_id == run.id)
        .order_by(SectionResearchEvidence.rank.asc())
    ).scalars().all())
    cov = (
        CoverageSummaryRead.model_validate(run.coverage_summary)
        if run.coverage_summary else None
    )
    return SectionResearchCurrentRead(
        run=SectionResearchRunRead.model_validate(run),
        evidence=[
            EvidenceItemRead.model_validate(e) for e in evidence
        ],
        coverage=cov,
    )


@router.get(
    "/{report_id}/manuscript/sections/{section_id}/research/runs",
    response_model=SectionResearchRunListResponse,
)
def list_section_research_runs(
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectionResearchRunListResponse:
    _load_chain(
        db, user_id=current_user.id,
        report_id=report_id, section_id=section_id,
    )
    base = select(SectionResearchRun).where(
        SectionResearchRun.manuscript_section_id == section_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(SectionResearchRun.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return SectionResearchRunListResponse(
        items=[SectionResearchRunRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/{report_id}/manuscript/sections/{section_id}/research/validate",
    response_model=SectionResearchValidationRead,
)
def validate_section_research(
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectionResearchValidationRead:
    _load_chain(
        db, user_id=current_user.id,
        report_id=report_id, section_id=section_id,
    )
    run = _load_current_run(db, section_id=section_id)
    errors: list[str] = []
    warnings: list[str] = []

    if run.context_hash is None or not run.context_hash:
        errors.append("missing_context_hash")
    if run.contract_hash is None or not run.contract_hash:
        errors.append("missing_contract_hash")
    if run.selected_evidence_count < 0:
        errors.append("negative_evidence_count")
    if not (0.0 <= float(run.coverage_score) <= 1.0):
        errors.append("coverage_out_of_range")

    evidence = list(db.execute(
        select(SectionResearchEvidence).where(
            SectionResearchEvidence.research_run_id == run.id
        )
    ).scalars().all())
    for e in evidence:
        if e.source_id is None:
            errors.append("evidence_missing_source")
        if e.rank < 1:
            errors.append("evidence_invalid_rank")

    if run.coverage_state == "insufficient":
        warnings.append("coverage_insufficient")

    return SectionResearchValidationRead(
        validation_status="valid" if not errors else "invalid",
        validation_errors=errors,
        warnings=warnings,
    )
