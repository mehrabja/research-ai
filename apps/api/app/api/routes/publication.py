"""M33 — Publication target + compliance API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import (
    PublicationComplianceNotFound,
    PublicationTargetNotFound,
)
from app.db.models.publication import (
    PublicationComplianceFinding,
    PublicationComplianceRun,
    PublicationTarget,
)
from app.db.models.user import User
from app.db.session import get_db
from app.domain.publication import ComplianceStatus
from app.schemas.publication import (
    PublicationChecklistRead,
    PublicationComplianceCurrentRead,
    PublicationComplianceFindingListResponse,
    PublicationComplianceFindingRead,
    PublicationComplianceRequest,
    PublicationComplianceResponse,
    PublicationComplianceRunListResponse,
    PublicationComplianceRunRead,
    PublicationComplianceValidationRead,
    PublicationTargetCreate,
    PublicationTargetListResponse,
    PublicationTargetRead,
    PublicationTargetSelectionRead,
    PublicationTargetSelectRequest,
)
from app.services.publication import jobs as pub_jobs
from app.services.publication import persistence as pub_persist
from app.services.publication import profiles as pub_profiles
from app.services.reports import get_report

router = APIRouter(tags=["publication"])


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


@router.post(
    "/publication-targets",
    response_model=PublicationTargetRead,
)
def create_publication_target(
    body: PublicationTargetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationTargetRead:
    # Target catalog is global (not per-project); auth required only.
    _ = current_user
    target = pub_profiles.create_target_profile(
        db,
        target_code=body.target_code,
        profile_version=body.profile_version,
        venue=body.venue,
        venue_type=body.venue_type,
        citation_style=body.citation_style,
        publisher=body.publisher,
        paper_types=body.paper_types,
        formatting_rules=body.formatting_rules,
        section_rules=body.section_rules,
        word_limits=body.word_limits,
        abstract_limits=body.abstract_limits,
        keyword_rules=body.keyword_rules,
        author_rules=body.author_rules,
        anonymity_rules=body.anonymity_rules,
        figure_table_rules=body.figure_table_rules,
        supplementary_rules=body.supplementary_rules,
        reference_rules=body.reference_rules,
        submission_checklist=body.submission_checklist,
        provenance=body.provenance,
    )
    db.commit()
    db.refresh(target)
    return PublicationTargetRead.model_validate(target)


@router.get(
    "/publication-targets",
    response_model=PublicationTargetListResponse,
)
def list_publication_targets(
    target_code: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationTargetListResponse:
    _ = current_user
    rows, total = pub_profiles.list_targets(
        db,
        target_code=target_code,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return PublicationTargetListResponse(
        items=[PublicationTargetRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/publication-targets/{target_id}",
    response_model=PublicationTargetRead,
)
def get_publication_target(
    target_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationTargetRead:
    _ = current_user
    target = pub_profiles.get_target(db, target_id=target_id)
    return PublicationTargetRead.model_validate(target)


# ---------------------------------------------------------------------------
# Per-report target selection
# ---------------------------------------------------------------------------


@router.post(
    "/reports/{report_id}/publication-target/select",
    response_model=PublicationTargetSelectionRead,
)
def select_target_for_report(
    report_id: uuid.UUID,
    body: PublicationTargetSelectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationTargetSelectionRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    selection = pub_profiles.select_target_for_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
        target_id=body.target_id,
        selection_note=body.selection_note,
    )
    db.commit()
    db.refresh(selection)
    return PublicationTargetSelectionRead.model_validate(selection)


@router.get(
    "/reports/{report_id}/publication-target/current",
    response_model=PublicationTargetSelectionRead,
)
def get_current_target_selection(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationTargetSelectionRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    selection = pub_profiles.get_current_selection(
        db, report_id=report_id,
    )
    if selection is None:
        raise PublicationTargetNotFound()
    return PublicationTargetSelectionRead.model_validate(selection)


# ---------------------------------------------------------------------------
# Compliance runs
# ---------------------------------------------------------------------------


def _load_current_run(
    db: Session, *, report_id: uuid.UUID,
) -> PublicationComplianceRun:
    run = db.execute(
        select(PublicationComplianceRun)
        .where(
            PublicationComplianceRun.report_id == report_id,
            PublicationComplianceRun.status
            == ComplianceStatus.COMPLETED.value,
        )
        .order_by(
            PublicationComplianceRun.created_at.desc(),
            PublicationComplianceRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise PublicationComplianceNotFound()
    return run


@router.post(
    "/reports/{report_id}/publication-compliance/generate",
    response_model=PublicationComplianceResponse,
)
def generate_publication_compliance(
    report_id: uuid.UUID,
    body: PublicationComplianceRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationComplianceResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    settings = get_settings()

    effective_async = bool(body.async_)
    if effective_async and not settings.publication_compliance_async_jobs:
        effective_async = False

    if effective_async:
        job_id = pub_jobs.enqueue_publication_compliance(
            db,
            report_id=report_id,
            manuscript_version_id=body.manuscript_version_id,
            target_id=body.target_id,
            user_id=current_user.id,
            force=body.force,
        )
        response.status_code = 202
        return PublicationComplianceResponse(
            status="queued", job_id=job_id,
        )

    persisted = pub_persist.run_m33_persisted(
        db,
        report_id=report_id,
        manuscript_version_id=body.manuscript_version_id,
        target_id=body.target_id,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    return PublicationComplianceResponse(
        status=persisted.run.status,
        run_id=persisted.run.id,
        context_hash=persisted.run.context_hash,
        gate=persisted.run.gate,
        finding_count=persisted.run.finding_count,
        blocking_count=persisted.run.blocking_count,
    )


@router.get(
    "/reports/{report_id}/publication-compliance/current",
    response_model=PublicationComplianceCurrentRead,
)
def get_current_publication_compliance(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationComplianceCurrentRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    return PublicationComplianceCurrentRead(
        run=PublicationComplianceRunRead.model_validate(run),
    )


@router.get(
    "/reports/{report_id}/publication-compliance/runs",
    response_model=PublicationComplianceRunListResponse,
)
def list_publication_compliance_runs(
    report_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationComplianceRunListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    base = select(PublicationComplianceRun).where(
        PublicationComplianceRun.report_id == report_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            PublicationComplianceRun.created_at.desc(),
            PublicationComplianceRun.id.desc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return PublicationComplianceRunListResponse(
        items=[
            PublicationComplianceRunRead.model_validate(r) for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/reports/{report_id}/publication-compliance/findings",
    response_model=PublicationComplianceFindingListResponse,
)
def list_publication_compliance_findings(
    report_id: uuid.UUID,
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationComplianceFindingListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    base = select(PublicationComplianceFinding).where(
        PublicationComplianceFinding.compliance_run_id == run.id
    )
    if category:
        base = base.where(
            PublicationComplianceFinding.category == category
        )
    if severity:
        base = base.where(
            PublicationComplianceFinding.severity == severity
        )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(PublicationComplianceFinding.created_at.asc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return PublicationComplianceFindingListResponse(
        items=[
            PublicationComplianceFindingRead.model_validate(r)
            for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.get(
    "/reports/{report_id}/publication-compliance/checklist",
    response_model=PublicationChecklistRead,
)
def get_publication_checklist(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationChecklistRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    return PublicationChecklistRead(
        run_id=run.id,
        target_id=run.target_id,
        target_profile_version=run.target_profile_version,
        gate=run.gate,
        checklist_state=run.checklist_state,
    )


@router.post(
    "/reports/{report_id}/publication-compliance/validate",
    response_model=PublicationComplianceValidationRead,
)
def validate_publication_compliance(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicationComplianceValidationRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    errors: list[str] = []
    warnings: list[str] = []

    if not run.context_hash:
        errors.append("missing_context_hash")
    if not run.target_profile_version:
        errors.append("missing_target_profile_version")

    findings = list(db.execute(
        select(PublicationComplianceFinding).where(
            PublicationComplianceFinding.compliance_run_id == run.id
        )
    ).scalars().all())
    for f in findings:
        if not f.rule_id:
            errors.append(f"finding_missing_rule_id:{f.id}")

    if run.warnings:
        warnings.extend(str(w) for w in run.warnings)

    return PublicationComplianceValidationRead(
        validation_status="valid" if not errors else "invalid",
        validation_errors=errors,
        warnings=warnings,
        gate=run.gate,
    )


# Ensure unused import is retained for future iterations
_ = PublicationTarget

__all__ = ["router"]
