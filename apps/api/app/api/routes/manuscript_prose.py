"""M28.5 — Manuscript prose API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import ManuscriptProseNotFound
from app.db.models.manuscript_prose import (
    ManuscriptProseRun,
    ManuscriptProseSection,
)
from app.db.models.user import User
from app.db.session import get_db
from app.domain.manuscript_prose import ProseRunStatus
from app.schemas.manuscript_prose import (
    ManuscriptProseCurrentRead,
    ManuscriptProseFinalizeRequest,
    ManuscriptProseGenerateRequest,
    ManuscriptProseGenerateResponse,
    ManuscriptProseRunListResponse,
    ManuscriptProseRunRead,
    ManuscriptProseSectionListResponse,
    ManuscriptProseSectionRead,
    ManuscriptProseSectionRegenerateRequest,
    ManuscriptProseValidationRead,
)
from app.services.manuscript_prose import jobs as mp_jobs
from app.services.manuscript_prose import persistence as mp_persist
from app.services.reports import get_report

router = APIRouter(prefix="/reports", tags=["manuscript-prose"])


def _load_current_run(
    db: Session, *, report_id: uuid.UUID,
) -> ManuscriptProseRun:
    run = db.execute(
        select(ManuscriptProseRun)
        .where(
            ManuscriptProseRun.report_id == report_id,
            ManuscriptProseRun.status == ProseRunStatus.COMPLETED.value,
        )
        .order_by(
            ManuscriptProseRun.created_at.desc(),
            ManuscriptProseRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise ManuscriptProseNotFound()
    return run


@router.post(
    "/{report_id}/manuscript/prose/generate",
    response_model=ManuscriptProseGenerateResponse,
)
def generate_manuscript_prose(
    report_id: uuid.UUID,
    body: ManuscriptProseGenerateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptProseGenerateResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    settings = get_settings()

    effective_async = bool(body.async_)
    if effective_async and not settings.manuscript_prose_async_jobs:
        effective_async = False

    if effective_async:
        job_id = mp_jobs.enqueue_manuscript_prose(
            db,
            report_id=report_id,
            base_manuscript_version_id=(
                body.base_manuscript_version_id
            ),
            user_id=current_user.id,
            mode=body.mode,
            force=body.force,
        )
        response.status_code = 202
        return ManuscriptProseGenerateResponse(
            status="queued", job_id=job_id,
        )

    persisted = mp_persist.run_m28_5_persisted(
        db,
        report_id=report_id,
        base_manuscript_version_id=body.base_manuscript_version_id,
        mode=body.mode,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    return ManuscriptProseGenerateResponse(
        status=persisted.run.status,
        run_id=persisted.run.id,
        context_hash=persisted.run.context_hash,
        section_count=int(persisted.run.section_count or 0),
        word_count=int(persisted.run.word_count or 0),
    )


@router.get(
    "/{report_id}/manuscript/prose/current",
    response_model=ManuscriptProseCurrentRead,
)
def get_current_manuscript_prose(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptProseCurrentRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    sections = list(db.execute(
        select(ManuscriptProseSection)
        .where(ManuscriptProseSection.run_id == run.id)
        .order_by(ManuscriptProseSection.display_order.asc())
    ).scalars().all())
    return ManuscriptProseCurrentRead(
        run=ManuscriptProseRunRead.model_validate(run),
        sections=[
            ManuscriptProseSectionRead.model_validate(s)
            for s in sections
        ],
    )


@router.get(
    "/{report_id}/manuscript/prose/runs",
    response_model=ManuscriptProseRunListResponse,
)
def list_manuscript_prose_runs(
    report_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptProseRunListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    base = select(ManuscriptProseRun).where(
        ManuscriptProseRun.report_id == report_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            ManuscriptProseRun.created_at.desc(),
            ManuscriptProseRun.id.desc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return ManuscriptProseRunListResponse(
        items=[ManuscriptProseRunRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/{report_id}/manuscript/prose/runs/{run_id}",
    response_model=ManuscriptProseCurrentRead,
)
def get_manuscript_prose_run(
    report_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptProseCurrentRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = db.execute(
        select(ManuscriptProseRun).where(
            ManuscriptProseRun.id == run_id,
            ManuscriptProseRun.report_id == report_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise ManuscriptProseNotFound()
    sections = list(db.execute(
        select(ManuscriptProseSection)
        .where(ManuscriptProseSection.run_id == run.id)
        .order_by(ManuscriptProseSection.display_order.asc())
    ).scalars().all())
    return ManuscriptProseCurrentRead(
        run=ManuscriptProseRunRead.model_validate(run),
        sections=[
            ManuscriptProseSectionRead.model_validate(s)
            for s in sections
        ],
    )


@router.get(
    "/{report_id}/manuscript/prose/sections",
    response_model=ManuscriptProseSectionListResponse,
)
def list_manuscript_prose_sections(
    report_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptProseSectionListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    base = select(ManuscriptProseSection).where(
        ManuscriptProseSection.run_id == run.id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(ManuscriptProseSection.display_order.asc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return ManuscriptProseSectionListResponse(
        items=[
            ManuscriptProseSectionRead.model_validate(s) for s in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/{report_id}/manuscript/prose/sections/{section_id}",
    response_model=ManuscriptProseSectionRead,
)
def get_manuscript_prose_section(
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptProseSectionRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    row = db.execute(
        select(ManuscriptProseSection).where(
            ManuscriptProseSection.id == section_id,
            ManuscriptProseSection.report_id == report_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise ManuscriptProseNotFound()
    return ManuscriptProseSectionRead.model_validate(row)


@router.post(
    "/{report_id}/manuscript/prose/validate",
    response_model=ManuscriptProseValidationRead,
)
def validate_manuscript_prose(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptProseValidationRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    errors: list[str] = []
    warnings: list[str] = []

    if not run.context_hash:
        errors.append("missing_context_hash")

    sections = list(db.execute(
        select(ManuscriptProseSection).where(
            ManuscriptProseSection.run_id == run.id
        )
    ).scalars().all())
    if not sections:
        errors.append("no_sections")
    for s in sections:
        if s.status == "insufficient_evidence":
            warnings.append(f"insufficient_evidence:{s.section_key}")

    if run.warnings:
        warnings.extend(str(w) for w in run.warnings)

    return ManuscriptProseValidationRead(
        validation_status="valid" if not errors else "invalid",
        validation_errors=errors,
        warnings=warnings,
    )


@router.post(
    "/{report_id}/manuscript/prose/regenerate-section",
    response_model=ManuscriptProseGenerateResponse,
)
def regenerate_manuscript_prose_section(
    report_id: uuid.UUID,
    body: ManuscriptProseSectionRegenerateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptProseGenerateResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    # Regenerating a single section is modelled as a full re-run with
    # force=True. Deterministic section-level caching happens inside
    # the persistence layer via context_hash on the run.
    persisted = mp_persist.run_m28_5_persisted(
        db,
        report_id=report_id,
        base_manuscript_version_id=body.manuscript_version_id,
        mode=body.mode,
        force=True,
        commit=True,
    )
    response.status_code = 200
    return ManuscriptProseGenerateResponse(
        status=persisted.run.status,
        run_id=persisted.run.id,
        context_hash=persisted.run.context_hash,
        section_count=int(persisted.run.section_count or 0),
        word_count=int(persisted.run.word_count or 0),
    )


@router.post(
    "/{report_id}/manuscript/prose/finalize",
    response_model=ManuscriptProseRunRead,
)
def finalize_manuscript_prose(
    report_id: uuid.UUID,
    body: ManuscriptProseFinalizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptProseRunRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = db.execute(
        select(ManuscriptProseRun).where(
            ManuscriptProseRun.id == body.run_id,
            ManuscriptProseRun.report_id == report_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise ManuscriptProseNotFound()
    if run.status != ProseRunStatus.COMPLETED.value:
        raise ManuscriptProseNotFound()
    # Finalize is currently a no-op beyond validation; the run is
    # already the canonical immutable output. Downstream M30/M31/M32
    # consult the latest completed run.
    return ManuscriptProseRunRead.model_validate(run)
