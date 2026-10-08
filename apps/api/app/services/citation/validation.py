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

    citation_ids = {cc.citation_id for cc in citations}
    idents: list[CitationIdentity] = []
    if citation_ids:
        idents = list(db.execute(
            select(CitationIdentity).where(
                CitationIdentity.id.in_(citation_ids)
            )
        ).scalars().all())
    by_id = {i.id: i for i in idents}

    # Every cited identity must resolve to a real source.
    if citation_ids:
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

    claim_by_id = {claim.id: claim for claim in claims}
    evidence_by_claim: dict[uuid.UUID, list[ClaimEvidence]] = {}
    for evidence in evs:
        evidence_by_claim.setdefault(evidence.claim_id, []).append(evidence)

    # Every ClaimCitation must be backed by evidence on the same claim.
    # This prevents a citation from appearing in the bibliography solely
    # because an identity resolved, without a persisted provenance edge.
    for citation in citations:
        claim = claim_by_id.get(citation.claim_id)
        if claim is None:
            errors.append(f"claim_citation_orphan_claim:{citation.id}")
            continue
        matching_evidence = [
            evidence
            for evidence in evidence_by_claim.get(claim.id, [])
            if evidence.source_id is not None
            and evidence.support_level == citation.support_level
        ]
        if not matching_evidence:
            errors.append(
                f"claim_citation_without_evidence:{citation.id}"
            )
            continue

        identity = by_id.get(citation.citation_id) if citation_ids else None
        if (
            identity is not None
            and identity.source_id is not None
            and not any(
                evidence.source_id == identity.source_id
                for evidence in matching_evidence
            )
        ):
                errors.append(
                    f"claim_citation_source_mismatch:{citation.id}"
                )

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
