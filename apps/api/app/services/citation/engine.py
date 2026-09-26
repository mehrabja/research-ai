"""M30 — Deterministic orchestrator. No persistence."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import CitationConfigurationInvalid
from app.domain.citation import (
    CitationStyle,
    ClaimStatus,
)
from app.services.citation import mapping as map_svc
from app.services.citation import prose as prose_svc
from app.services.citation.claims import extract_claims


@dataclass
class M30Result:
    report_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    context_hash: str
    citation_style: str
    prose_available: bool
    claims: list = field(default_factory=list)
    mappings: dict = field(default_factory=dict)  # claim_id -> [MappedEvidence]
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0


def _current_m29_run_id(
    db: Session, *, project_id: uuid.UUID,
) -> uuid.UUID | None:
    from sqlalchemy import select

    from app.db.models.technical_intelligence import (
        TechnicalIntelligenceRun,
    )
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
    return run.id if run else None


def run_citation_engine(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    project_id: uuid.UUID,
    citation_style: str,
    context_hash: str,
) -> M30Result:
    started = time.perf_counter()
    settings = get_settings()
    if not settings.citation_enabled:
        raise CitationConfigurationInvalid("citation is disabled")

    if citation_style not in (
        CitationStyle.NUMERIC.value, CitationStyle.AUTHOR_YEAR.value,
    ):
        raise CitationConfigurationInvalid(
            f"unknown citation style: {citation_style}"
        )

    warnings: list[str] = []

    prose = prose_svc.get_manuscript_prose(
        db, manuscript_version_id=manuscript_version_id,
    )
    prose_available = prose is not None and not prose.is_empty

    if not prose_available:
        warnings.append("manuscript_prose_not_available")
        return M30Result(
            report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
            citation_style=citation_style,
            prose_available=False,
            claims=[],
            mappings={},
            warnings=warnings,
            duration_ms=int(
                (time.perf_counter() - started) * 1000
            ),
        )

    extracted = extract_claims(
        db, manuscript_version_id=manuscript_version_id,
    )
    max_claims = int(settings.citation_max_claims)
    if len(extracted) > max_claims:
        warnings.append(
            f"claims_truncated:{len(extracted)}->{max_claims}"
        )
        extracted = extracted[:max_claims]

    m29_run_id = _current_m29_run_id(db, project_id=project_id)
    mappings: dict = {}
    for c in extracted:
        mappings[c.claim_hash] = map_svc.map_evidence_for_claim(
            db,
            claim=c,
            project_id=project_id,
            m29_run_id=m29_run_id,
        )

    _ = ClaimStatus  # reserved
    return M30Result(
        report_id=report_id,
        manuscript_version_id=manuscript_version_id,
        context_hash=context_hash,
        citation_style=citation_style,
        prose_available=True,
        claims=extracted,
        mappings=mappings,
        warnings=warnings,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


__all__ = ["M30Result", "run_citation_engine"]
