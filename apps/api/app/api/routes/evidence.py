"""Claim-centric evidence matrix endpoint."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.citation import Claim, ClaimCitation, ClaimEvidence, CitationRun
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.evidence import (
    EvidenceMatrixCitation,
    EvidenceMatrixClaim,
    EvidenceMatrixEvidence,
    EvidenceMatrixResponse,
)
from app.services.reports import get_report


router = APIRouter(prefix="/reports", tags=["evidence"])


@router.get(
    "/{report_id}/evidence/matrix",
    response_model=EvidenceMatrixResponse,
)
def get_matrix(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceMatrixResponse:
    get_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
    )
    run = db.execute(
        select(CitationRun)
        .where(
            CitationRun.report_id == report_id,
            CitationRun.status == "completed",
        )
        .order_by(
            CitationRun.created_at.desc(),
            CitationRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()

    if run is None:
        raise ValueError("No completed citation run exists.")

    claims = list(
        db.execute(
            select(Claim)
            .where(Claim.citation_run_id == run.id)
            .order_by(Claim.created_at.asc(), Claim.id.asc())
        ).scalars().all()
    )

    result: list[EvidenceMatrixClaim] = []
    for claim in claims:
        evidence_rows = list(
            db.execute(
                select(ClaimEvidence)
                .where(ClaimEvidence.claim_id == claim.id)
                .order_by(
                    ClaimEvidence.relevance_score.desc(),
                    ClaimEvidence.id.asc(),
                )
            ).scalars().all()
        )
        citation_rows = list(
            db.execute(
                select(ClaimCitation)
                .where(ClaimCitation.claim_id == claim.id)
                .order_by(
                    ClaimCitation.citation_order.asc().nullslast(),
                    ClaimCitation.id.asc(),
                )
            ).scalars().all()
        )
        result.append(
            EvidenceMatrixClaim(
                id=claim.id,
                manuscript_section_id=claim.manuscript_section_id,
                claim_text=claim.claim_text,
                claim_type=claim.claim_type,
                status=claim.status,
                evidence=[
                    EvidenceMatrixEvidence(
                        id=row.id,
                        evidence_type=row.evidence_type,
                        evidence_id=row.evidence_id,
                        source_id=row.source_id,
                        support_level=row.support_level,
                        relevance_score=float(row.relevance_score),
                        provenance=dict(row.provenance or {}),
                    )
                    for row in evidence_rows
                ],
                citations=[
                    EvidenceMatrixCitation(
                        id=row.id,
                        citation_id=row.citation_id,
                        relation_type=row.relation_type,
                        support_level=row.support_level,
                        relevance_score=float(row.relevance_score),
                        citation_order=row.citation_order,
                        paragraph_index=row.paragraph_index,
                        sentence_index=row.sentence_index,
                    )
                    for row in citation_rows
                ],
            )
        )

    return EvidenceMatrixResponse(
        report_id=report_id,
        citation_run_id=run.id,
        manuscript_version_id=run.manuscript_version_id,
        coverage_score=float(run.coverage_score),
        unsupported_count=run.unsupported_count,
        claims=result,
    )
