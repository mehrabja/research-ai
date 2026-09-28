"""M30 — Citation Engine API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import CitationInvalid, CitationNotFound
from app.db.models.citation import (
    CitationIdentity,
    CitationRun,
    Claim,
    ClaimCitation,
    ClaimEvidence,
)
from app.db.models.user import User
from app.db.session import get_db
from app.domain.citation import CitationRunStatus, CitationStyle
from app.schemas.citation import (
    BibliographyEntryRead,
    BibliographyRead,
    CitationCurrentRead,
    ClaimCitationRead,
    ClaimEvidenceRead,
    EvidenceMatrixRead,
    EvidenceMatrixRow,
    CitationGenerateRequest,
    CitationGenerateResponse,
    CitationRunListResponse,
    CitationRunRead,
    CitationValidationRead,
    ClaimRead,
)
from app.services.citation import bibliography as bib_svc
from app.services.citation import jobs as cit_jobs
from app.services.citation import persistence as cit_persist
from app.services.citation import validation as val_svc
from app.services.reports import get_report

router = APIRouter(prefix="/reports", tags=["citations"])


def _load_current_run(
    db: Session, *, report_id: uuid.UUID,
) -> CitationRun:
    run = db.execute(
        select(CitationRun)
        .where(
            CitationRun.report_id == report_id,
            CitationRun.status == CitationRunStatus.COMPLETED.value,
        )
        .order_by(
            CitationRun.created_at.desc(),
            CitationRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise CitationNotFound()
    return run


@router.post(
    "/{report_id}/citations/generate",
    response_model=CitationGenerateResponse,
)
def generate_citations(
    report_id: uuid.UUID,
    body: CitationGenerateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CitationGenerateResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)

    if body.citation_style not in (
        CitationStyle.NUMERIC.value, CitationStyle.AUTHOR_YEAR.value,
    ):
        raise CitationInvalid("unknown citation style")

    settings = get_settings()
    effective_async = bool(body.async_)
    if effective_async and not settings.citation_async_jobs:
        effective_async = False

    if effective_async:
        job_id = cit_jobs.enqueue_citation_run(
            db,
            report_id=report_id,
            manuscript_version_id=body.manuscript_version_id,
            user_id=current_user.id,
            citation_style=body.citation_style,
            force=body.force,
        )
        response.status_code = 202
        return CitationGenerateResponse(
            status="queued", job_id=job_id,
        )

    persisted = cit_persist.run_citation_persisted(
        db,
        user_id=current_user.id,
        report_id=report_id,
        manuscript_version_id=body.manuscript_version_id,
        citation_style=body.citation_style,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    return CitationGenerateResponse(
        status=persisted.run.status,
        run_id=persisted.run.id,
        context_hash=persisted.run.context_hash,
        claim_count=persisted.run.claim_count,
        citation_count=persisted.run.citation_count,
        unsupported_count=persisted.run.unsupported_count,
        coverage_score=float(persisted.run.coverage_score),
    )


@router.get(
    "/{report_id}/citations/current",
    response_model=CitationCurrentRead,
)
def get_current_citations(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CitationCurrentRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    claims = list(db.execute(
        select(Claim)
        .where(Claim.citation_run_id == run.id)
        .order_by(Claim.created_at.asc())
    ).scalars().all())
    return CitationCurrentRead(
        run=CitationRunRead.model_validate(run),
        claims=[ClaimRead.model_validate(c) for c in claims],
    )


@router.get(
    "/{report_id}/evidence/matrix",
    response_model=EvidenceMatrixRead,
)
def get_evidence_matrix(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceMatrixRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    claims = list(
        db.execute(
            select(Claim)
            .where(Claim.citation_run_id == run.id)
            .order_by(Claim.created_at.asc(), Claim.id.asc())
        ).scalars().all()
    )
    claim_ids = [claim.id for claim in claims]
    evidence_rows = (
        list(
            db.execute(
                select(ClaimEvidence)
                .where(ClaimEvidence.claim_id.in_(claim_ids))
                .order_by(
                    ClaimEvidence.claim_id.asc(),
                    ClaimEvidence.relevance_score.desc(),
                    ClaimEvidence.id.asc(),
                )
            ).scalars().all()
        )
        if claim_ids else []
    )
    citation_rows = (
        list(
            db.execute(
                select(ClaimCitation)
                .where(ClaimCitation.claim_id.in_(claim_ids))
                .order_by(
                    ClaimCitation.claim_id.asc(),
                    ClaimCitation.citation_order.asc().nullslast(),
                    ClaimCitation.id.asc(),
                )
            ).scalars().all()
        )
        if claim_ids else []
    )
    evidence_by_claim: dict[uuid.UUID, list[ClaimEvidence]] = {}
    citation_by_claim: dict[uuid.UUID, list[ClaimCitation]] = {}
    for evidence_row in evidence_rows:
        evidence_by_claim.setdefault(evidence_row.claim_id, []).append(evidence_row)
    for citation_row in citation_rows:
        citation_by_claim.setdefault(citation_row.claim_id, []).append(citation_row)

    return EvidenceMatrixRead(
        report_id=report_id,
        citation_run_id=run.id,
        rows=[
            EvidenceMatrixRow(
                claim=ClaimRead.model_validate(claim),
                evidence=[
                    ClaimEvidenceRead.model_validate(e)
                    for e in evidence_by_claim.get(claim.id, [])
                ],
                citations=[
                    ClaimCitationRead.model_validate(cc)
                    for cc in citation_by_claim.get(claim.id, [])
                ],
            )
            for claim in claims
        ],
    )


@router.get(
    "/{report_id}/citations/history",
    response_model=CitationRunListResponse,
)
def list_citation_runs(
    report_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CitationRunListResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    base = select(CitationRun).where(
        CitationRun.report_id == report_id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            CitationRun.created_at.desc(),
            CitationRun.id.desc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return CitationRunListResponse(
        items=[CitationRunRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/{report_id}/citations/validate",
    response_model=CitationValidationRead,
)
def validate_citations(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CitationValidationRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)
    result = val_svc.validate_citation_run(db, run=run)
    return CitationValidationRead(
        validation_status=result.status,
        validation_errors=result.errors,
        warnings=result.warnings,
    )


@router.get(
    "/{report_id}/citations/bibliography",
    response_model=BibliographyRead,
)
def get_bibliography(
    report_id: uuid.UUID,
    citation_style: str = Query(default="author_year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BibliographyRead:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = _load_current_run(db, report_id=report_id)

    # Only identities actually cited by this run.
    citations = list(db.execute(
        select(ClaimCitation)
        .join(Claim, ClaimCitation.claim_id == Claim.id)
        .where(Claim.citation_run_id == run.id)
    ).scalars().all())
    cited_ids = {cc.citation_id for cc in citations}
    if not cited_ids:
        return BibliographyRead(
            style=citation_style, entries=[],
            unresolved_identity_ids=[],
        )

    idents = list(db.execute(
        select(CitationIdentity).where(
            CitationIdentity.id.in_(cited_ids)
        )
    ).scalars().all())

    # First-appearance order from citation_order fields
    first_seen: dict[str, int] = {}
    for cc in citations:
        if cc.citation_order is None:
            continue
        cid = str(cc.citation_id)
        prev = first_seen.get(cid)
        if prev is None or cc.citation_order < prev:
            first_seen[cid] = cc.citation_order

    result = bib_svc.build_bibliography(
        db,
        report_id=report_id,
        identities=idents,
        first_seen=first_seen,
        style=citation_style,
    )
    return BibliographyRead(
        style=citation_style,
        entries=[
            BibliographyEntryRead(
                citation_id=e.citation_id,
                source_id=e.source_id,
                label=e.label,
                rendered=e.rendered,
                order=e.order,
                display_key=e.display_key,
            )
            for e in result.entries
        ],
        unresolved_identity_ids=result.unresolved_identity_ids,
    )
