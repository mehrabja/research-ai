"""Authorized claim-centric evidence matrix service."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import ReportNotFound
from app.db.models.citation import Claim, ClaimEvidence, CitationRun
from app.db.models.manuscript import ManuscriptVersion
from app.db.models.report import Report
from app.db.models.source import Source


def _require_report(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Report:
    report = db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.user_id == user_id,
        )
    ).scalar_one_or_none()
    if report is None:
        raise ReportNotFound()
    return report


def _claim_in_report(
    db: Session,
    *,
    claim_id: uuid.UUID,
    report_id: uuid.UUID,
) -> Claim:
    claim = db.execute(
        select(Claim)
        .join(CitationRun, CitationRun.id == Claim.citation_run_id)
        .where(
            Claim.id == claim_id,
            CitationRun.report_id == report_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if claim is None:
        raise ValueError("claim not found")
    return claim


def list_matrix(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[tuple[Claim, list[ClaimEvidence]]]:
    _require_report(db, report_id=report_id, user_id=user_id)
    claims = list(
        db.execute(
            select(Claim)
            .join(CitationRun, CitationRun.id == Claim.citation_run_id)
            .where(CitationRun.report_id == report_id)
            .order_by(Claim.created_at.asc())
        ).scalars().all()
    )
    links_by_claim: dict[uuid.UUID, list[ClaimEvidence]] = {
        claim.id: [] for claim in claims
    }
    if claims:
        links = db.execute(
            select(ClaimEvidence).where(
                ClaimEvidence.claim_id.in_(links_by_claim)
            )
        ).scalars().all()
        for link in links:
            links_by_claim[link.claim_id].append(link)
    return [(claim, links_by_claim[claim.id]) for claim in claims]


def create_claim(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    citation_run_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    manuscript_section_id: uuid.UUID | None,
    claim_text: str,
    claim_type: str,
    location: dict[str, Any] | None,
) -> Claim:
    _require_report(db, report_id=report_id, user_id=user_id)
    run = db.execute(
        select(CitationRun).where(
            CitationRun.id == citation_run_id,
            CitationRun.report_id == report_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise ValueError("citation run does not belong to report")
    manuscript_version = db.execute(
        select(ManuscriptVersion).where(
            ManuscriptVersion.id == manuscript_version_id,
            ManuscriptVersion.manuscript.has(report_id=report_id),
        )
    ).scalar_one_or_none()
    if manuscript_version is None:
        raise ValueError("manuscript version does not belong to report")
    normalized = " ".join(claim_text.split())
    claim_hash = hashlib.sha256(normalized.lower().encode("utf-8")).hexdigest()
    row = Claim(
        citation_run_id=citation_run_id,
        manuscript_version_id=manuscript_version_id,
        manuscript_section_id=manuscript_section_id,
        claim_hash=claim_hash,
        claim_text=claim_text.strip(),
        claim_type=claim_type,
        location=location,
        status="extracted",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_evidence(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    claim_id: uuid.UUID,
    evidence_type: str,
    evidence_id: uuid.UUID,
    source_id: uuid.UUID | None,
    support_level: str,
    relevance_score: Any,
    provenance: dict[str, Any],
) -> ClaimEvidence:
    _require_report(db, report_id=report_id, user_id=user_id)
    claim = _claim_in_report(
        db, claim_id=claim_id, report_id=report_id
    )
    if source_id is not None:
        source = db.execute(
            select(Source).where(
                Source.id == source_id,
                Source.report_id == report_id,
            )
        ).scalar_one_or_none()
        if source is None:
            raise ValueError("source does not belong to report")
    existing = db.execute(
        select(ClaimEvidence).where(
            ClaimEvidence.claim_id == claim.id,
            ClaimEvidence.evidence_type == evidence_type,
            ClaimEvidence.evidence_id == evidence_id,
            ClaimEvidence.source_id == source_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = ClaimEvidence(
        claim_id=claim.id,
        evidence_type=evidence_type,
        evidence_id=evidence_id,
        source_id=source_id,
        support_level=support_level,
        relevance_score=relevance_score,
        provenance=provenance,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def remove_evidence(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    claim_id: uuid.UUID,
    evidence_link_id: uuid.UUID,
) -> None:
    _require_report(db, report_id=report_id, user_id=user_id)
    _claim_in_report(db, claim_id=claim_id, report_id=report_id)
    db.execute(
        delete(ClaimEvidence).where(
            ClaimEvidence.id == evidence_link_id,
            ClaimEvidence.claim_id == claim_id,
        )
    )
    db.commit()
