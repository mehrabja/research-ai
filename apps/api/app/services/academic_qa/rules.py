"""M31 — Deterministic QA rules.

Each rule takes a snapshot and returns 0..N findings.
No LLM. No fabrication. Facts come from persisted entities.
"""
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
from app.db.models.manuscript import ManuscriptSection
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.db.models.source import Source
from app.domain.academic_qa import (
    QACategory,
    QASeverity,
)
from app.services.academic_qa.findings import QAFinding


@dataclass
class QASnapshot:
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    sections: list[ManuscriptSection] = field(default_factory=list)
    m28_evidence_by_section: dict[uuid.UUID, list] = field(
        default_factory=dict
    )
    m30_run_id: uuid.UUID | None = None
    m30_claims: list[Claim] = field(default_factory=list)
    m30_claim_evidences: list[ClaimEvidence] = field(default_factory=list)
    m30_claim_citations: list[ClaimCitation] = field(default_factory=list)
    m30_identities: list[CitationIdentity] = field(default_factory=list)
    report_source_ids: set[uuid.UUID] = field(default_factory=set)


def build_snapshot(
    db: Session,
    *,
    manuscript_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
) -> QASnapshot:
    sections = list(db.execute(
        select(ManuscriptSection)
        .where(
            ManuscriptSection.manuscript_version_id
            == manuscript_version_id
        )
        .order_by(ManuscriptSection.display_order.asc())
    ).scalars().all())

    # M28 evidence grouped by section
    run_rows = list(db.execute(
        select(
            SectionResearchRun.id,
            SectionResearchRun.manuscript_section_id,
        )
        .where(
            SectionResearchRun.manuscript_version_id
            == manuscript_version_id,
            SectionResearchRun.status == "completed",
        )
    ).all())
    run_to_section: dict[uuid.UUID, uuid.UUID] = {}
    for row in run_rows:
        rid = row[0]
        sid = row[1]
        if sid is not None:
            run_to_section[rid] = sid

    ev_by_section: dict[uuid.UUID, list] = {}
    if run_to_section:
        ev_rows = list(db.execute(
            select(SectionResearchEvidence)
            .where(SectionResearchEvidence.research_run_id.in_(
                list(run_to_section.keys())
            ))
        ).scalars().all())
        for e in ev_rows:
            sid = run_to_section.get(e.research_run_id)
            if sid:
                ev_by_section.setdefault(sid, []).append(e)

    # M30 — latest completed run for report
    m30_run = db.execute(
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
    m30_run_id = m30_run.id if m30_run else None

    claims: list[Claim] = []
    evidences: list[ClaimEvidence] = []
    citations: list[ClaimCitation] = []
    identities: list[CitationIdentity] = []
    if m30_run_id is not None:
        claims = list(db.execute(
            select(Claim).where(Claim.citation_run_id == m30_run_id)
        ).scalars().all())
        if claims:
            claim_ids = [c.id for c in claims]
            evidences = list(db.execute(
                select(ClaimEvidence).where(
                    ClaimEvidence.claim_id.in_(claim_ids)
                )
            ).scalars().all())
            citations = list(db.execute(
                select(ClaimCitation).where(
                    ClaimCitation.claim_id.in_(claim_ids)
                )
            ).scalars().all())
            if citations:
                id_set = {cc.citation_id for cc in citations}
                identities = list(db.execute(
                    select(CitationIdentity).where(
                        CitationIdentity.id.in_(id_set)
                    )
                ).scalars().all())

    source_ids = {
        r[0]
        for r in db.execute(
            select(Source.id).where(Source.report_id == report_id)
        ).all()
    }

    return QASnapshot(
        project_id=project_id,
        report_id=report_id,
        manuscript_id=manuscript_id,
        manuscript_version_id=manuscript_version_id,
        sections=sections,
        m28_evidence_by_section=ev_by_section,
        m30_run_id=m30_run_id,
        m30_claims=claims,
        m30_claim_evidences=evidences,
        m30_claim_citations=citations,
        m30_identities=identities,
        report_source_ids=source_ids,
    )

# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------


def rule_missing_m30_run(snap: QASnapshot) -> list[QAFinding]:
    if snap.m30_run_id is None:
        return [QAFinding(
            rule_id="citation.m30_run_missing",
            category=QACategory.CITATION_INTEGRITY.value,
            severity=QASeverity.WARNING.value,
            title="No completed citation run",
            message=(
                "No completed M30 citation run is available for this "
                "report. Citation integrity cannot be fully evaluated."
            ),
        )]
    return []


def rule_section_without_evidence(snap: QASnapshot) -> list[QAFinding]:
    out: list[QAFinding] = []
    for s in snap.sections:
        if s.status != "active":
            continue
        if s.required and not snap.m28_evidence_by_section.get(s.id):
            out.append(QAFinding(
                rule_id="evidence.section_without_coverage",
                category=QACategory.EVIDENCE_COVERAGE.value,
                severity=QASeverity.WARNING.value,
                title=f"Section '{s.section_key}' has no evidence",
                message=(
                    f"Required section '{s.section_key}' has no M28 "
                    "evidence snapshot."
                ),
                manuscript_section_id=s.id,
                location={"section_key": s.section_key},
            ))
    return out


def rule_unsupported_claims(snap: QASnapshot) -> list[QAFinding]:
    out: list[QAFinding] = []
    for c in snap.m30_claims:
        if c.status == "unsupported":
            out.append(QAFinding(
                rule_id="claim.unsupported",
                category=QACategory.CLAIM_QUALITY.value,
                severity=QASeverity.WARNING.value,
                title="Unsupported claim",
                message=f"Claim has no supporting evidence: {c.claim_text[:120]}",
                claim_id=c.id,
                manuscript_section_id=c.manuscript_section_id,
                evidence={"claim_hash": c.claim_hash},
            ))
    return out


def rule_claim_without_evidence(snap: QASnapshot) -> list[QAFinding]:
    with_ev = {e.claim_id for e in snap.m30_claim_evidences}
    out: list[QAFinding] = []
    for c in snap.m30_claims:
        if c.id not in with_ev:
            out.append(QAFinding(
                rule_id="claim.no_evidence_record",
                category=QACategory.EVIDENCE_COVERAGE.value,
                severity=QASeverity.ERROR.value,
                title="Claim has no evidence record",
                message=(
                    f"Claim {c.id} has zero ClaimEvidence rows. "
                    "This is a data integrity issue."
                ),
                claim_id=c.id,
            ))
    return out


def rule_orphan_claim_citations(snap: QASnapshot) -> list[QAFinding]:
    ident_by_id = {i.id: i for i in snap.m30_identities}
    out: list[QAFinding] = []
    for cc in snap.m30_claim_citations:
        ident = ident_by_id.get(cc.citation_id)
        if ident is None:
            out.append(QAFinding(
                rule_id="citation.identity_missing",
                category=QACategory.CITATION_INTEGRITY.value,
                severity=QASeverity.BLOCKING.value,
                title="ClaimCitation has no resolvable identity",
                message=(
                    f"ClaimCitation {cc.id} points to a missing "
                    "CitationIdentity."
                ),
                claim_id=cc.claim_id,
                citation_id=cc.citation_id,
            ))
            continue
        if ident.source_id not in snap.report_source_ids:
            out.append(QAFinding(
                rule_id="citation.source_missing",
                category=QACategory.CITATION_INTEGRITY.value,
                severity=QASeverity.BLOCKING.value,
                title="Cited source is missing from report",
                message=(
                    f"CitationIdentity {ident.id} references source "
                    f"{ident.source_id} which is not in this report."
                ),
                claim_id=cc.claim_id,
                citation_id=ident.id,
            ))
    return out


def rule_sections_structure(snap: QASnapshot) -> list[QAFinding]:
    """Detect duplicate display_order and duplicate section_key."""
    out: list[QAFinding] = []
    seen_keys: set[str] = set()
    seen_orders: set[int] = set()
    for s in snap.sections:
        if s.section_key in seen_keys:
            out.append(QAFinding(
                rule_id="structure.duplicate_section_key",
                category=QACategory.STRUCTURAL_CONSISTENCY.value,
                severity=QASeverity.ERROR.value,
                title=f"Duplicate section_key '{s.section_key}'",
                message=(
                    "Two active sections share the same section_key "
                    "in this manuscript version."
                ),
                manuscript_section_id=s.id,
            ))
        seen_keys.add(s.section_key)
        if s.display_order in seen_orders:
            out.append(QAFinding(
                rule_id="structure.duplicate_display_order",
                category=QACategory.STRUCTURAL_CONSISTENCY.value,
                severity=QASeverity.ERROR.value,
                title=f"Duplicate display_order {s.display_order}",
                message=(
                    "Two active sections share the same display_order."
                ),
                manuscript_section_id=s.id,
            ))
        seen_orders.add(s.display_order)
    return out


ALL_RULES = (
    rule_missing_m30_run,
    rule_section_without_evidence,
    rule_unsupported_claims,
    rule_claim_without_evidence,
    rule_orphan_claim_citations,
    rule_sections_structure,
)


def run_all_rules(snap: QASnapshot) -> list[QAFinding]:
    out: list[QAFinding] = []
    for rule in ALL_RULES:
        try:
            out.extend(rule(snap))
        except Exception as exc:  # noqa: BLE001
            # Rule failure becomes a diagnostic, not a crash.
            out.append(QAFinding(
                rule_id=f"internal.rule_failed:{rule.__name__}",
                category=QACategory.STRUCTURAL_CONSISTENCY.value,
                severity=QASeverity.ERROR.value,
                title=f"QA rule failed: {rule.__name__}",
                message=str(exc)[:300],
                classification="deterministic",
            ))
    return out


__all__ = [
    "QASnapshot",
    "build_snapshot",
    "ALL_RULES",
    "run_all_rules",
]
