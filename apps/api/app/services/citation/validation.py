"""M30 — Real validation. No placeholder loops."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.citation import (
    CitationIdentity,
    CitationRun,
    Claim,
    ClaimCitation,
    ClaimEvidence,
)
from app.db.models.source import Source


@dataclass
class ValidationResult:
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_citation_run(
    db: Session, *, run: CitationRun,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not run.context_hash:
        errors.append("missing_context_hash")

    claims = list(db.execute(
        select(Claim).where(Claim.citation_run_id == run.id)
    ).scalars().all())
    if len(claims) != run.claim_count:
        errors.append(
            f"claim_count_mismatch:{len(claims)}!={run.claim_count}"
        )

    for c in claims:
        if c.manuscript_version_id != run.manuscript_version_id:
            errors.append(f"claim_version_mismatch:{c.id}")

    citations = list(db.execute(
        select(ClaimCitation)
        .join(Claim, ClaimCitation.claim_id == Claim.id)
        .where(Claim.citation_run_id == run.id)
    ).scalars().all())

    # Every cited identity must resolve to a real source.
    citation_ids = {cc.citation_id for cc in citations}
    if citation_ids:
        idents = list(db.execute(
            select(CitationIdentity).where(
                CitationIdentity.id.in_(citation_ids)
            )
        ).scalars().all())
        by_id = {i.id: i for i in idents}
        src_ids = [
            i.source_id for i in idents if i.source_id is not None
        ]
        if src_ids:
            real_srcs = {
                s.id
                for s in db.execute(
                    select(Source).where(Source.id.in_(src_ids))
                ).scalars().all()
            }
        else:
            real_srcs = set()
        for cid in citation_ids:
            ident = by_id.get(cid)
            if ident is None:
                errors.append(f"claim_citation_missing_identity:{cid}")
                continue
            if ident.source_id not in real_srcs:
                errors.append(f"claim_citation_unresolved_source:{cid}")

    # Every ClaimEvidence must have provenance.
    evs = list(db.execute(
        select(ClaimEvidence)
        .join(Claim, ClaimEvidence.claim_id == Claim.id)
        .where(Claim.citation_run_id == run.id)
    ).scalars().all())
    for e in evs:
        if not e.provenance:
            errors.append(f"claim_evidence_missing_provenance:{e.id}")

    if run.unsupported_count > 0:
        warnings.append(
            f"unsupported_claims_present:{run.unsupported_count}"
        )
    if run.duplicate_reference_count > 0:
        warnings.append(
            f"duplicate_references_present:"
            f"{run.duplicate_reference_count}"
        )
    if (run.warnings or []) and "manuscript_prose_not_available" in (
        run.warnings or []
    ):
        warnings.append("manuscript_prose_not_available")

    _ = uuid  # reserved
    return ValidationResult(
        status="valid" if not errors else "invalid",
        errors=errors,
        warnings=warnings,
    )


__all__ = ["ValidationResult", "validate_citation_run"]
