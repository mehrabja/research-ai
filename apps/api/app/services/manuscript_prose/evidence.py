"""M28.5 — Evidence packet assembly.

For each manuscript section we produce a bounded packet containing:
  * the section contract
  * M28 evidence rows (scoped to the section's SectionResearchRun)
  * M29 technical facts / experiment results / metrics (project-scoped,
    from the explicitly selected M29 run)
  * M30 citation identities that are already linked to this report
    (optional; M28.5 does NOT synthesize citations)
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
)
from app.db.models.experiment_result import ExperimentResult
from app.db.models.metric import Metric
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.db.models.technical_fact import TechnicalFact
from app.db.models.technical_intelligence import (
    TechnicalIntelligenceRun,
)


@dataclass
class EvidenceItem:
    evidence_id: uuid.UUID
    source_id: uuid.UUID | None
    excerpt: str
    rank: int
    evidence_role: str
    matched_requirement_keys: list[str] = field(default_factory=list)


@dataclass
class TechnicalFactItem:
    fact_id: uuid.UUID
    fact_type: str
    fact_key: str
    fact_value: str | None
    normalized_value: str | None


@dataclass
class ExperimentResultItem:
    result_id: uuid.UUID
    result_type: str
    name: str
    experiment_key: str | None


@dataclass
class MetricItem:
    metric_id: uuid.UUID
    name: str
    normalized_name: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    split: str | None
    direction: str | None


@dataclass
class CitationCandidate:
    identity_id: uuid.UUID
    source_id: uuid.UUID
    display_label: str | None


@dataclass
class EvidencePacket:
    section_key: str
    section_type: str
    display_order: int
    title: str
    research_objective: str | None
    m28_items: list[EvidenceItem] = field(default_factory=list)
    technical_facts: list[TechnicalFactItem] = field(default_factory=list)
    experiment_results: list[ExperimentResultItem] = field(
        default_factory=list
    )
    metrics: list[MetricItem] = field(default_factory=list)
    citation_candidates: list[CitationCandidate] = field(
        default_factory=list
    )
    warnings: list[str] = field(default_factory=list)

    @property
    def has_any_evidence(self) -> bool:
        return bool(
            self.m28_items
            or self.technical_facts
            or self.experiment_results
            or self.metrics
        )


def _load_m28_evidence(
    db: Session,
    *,
    manuscript_version_id: uuid.UUID,
    manuscript_section_id: uuid.UUID,
    max_items: int,
) -> list[EvidenceItem]:
    runs = list(db.execute(
        select(SectionResearchRun.id).where(
            SectionResearchRun.manuscript_version_id
            == manuscript_version_id,
            SectionResearchRun.manuscript_section_id
            == manuscript_section_id,
            SectionResearchRun.status == "completed",
        ).order_by(
            SectionResearchRun.created_at.desc(),
            SectionResearchRun.id.desc(),
        ).limit(1)
    ).all())
    if not runs:
        return []
    run_id = runs[0][0]
    rows = list(db.execute(
        select(SectionResearchEvidence)
        .where(SectionResearchEvidence.research_run_id == run_id)
        .order_by(SectionResearchEvidence.rank.asc())
        .limit(max_items)
    ).scalars().all())
    out: list[EvidenceItem] = []
    for e in rows:
        out.append(EvidenceItem(
            evidence_id=e.id,
            source_id=e.source_id,
            excerpt=(e.excerpt or "")[:1000],
            rank=int(e.rank),
            evidence_role=e.evidence_role,
            matched_requirement_keys=list(
                e.matched_requirement_keys or []
            ),
        ))
    return out


def _load_technical_intelligence(
    db: Session,
    *,
    project_id: uuid.UUID,
    max_items: int,
) -> tuple[
    list[TechnicalFactItem],
    list[ExperimentResultItem],
    list[MetricItem],
]:
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
    if run is None:
        return [], [], []

    facts = list(db.execute(
        select(TechnicalFact)
        .where(
            TechnicalFact.technical_intelligence_run_id == run.id,
            TechnicalFact.status.in_(("extracted", "validated")),
        )
        .order_by(TechnicalFact.created_at.asc())
        .limit(max_items)
    ).scalars().all())

    results = list(db.execute(
        select(ExperimentResult)
        .where(
            ExperimentResult.technical_intelligence_run_id == run.id,
            ExperimentResult.status.in_(("parsed", "validated")),
        )
        .order_by(ExperimentResult.created_at.asc())
        .limit(max_items)
    ).scalars().all())

    metrics = list(db.execute(
        select(Metric)
        .where(
            Metric.technical_intelligence_run_id == run.id,
            Metric.status.in_(("parsed", "validated")),
        )
        .order_by(Metric.created_at.asc())
        .limit(max_items)
    ).scalars().all())

    fact_items = [
        TechnicalFactItem(
            fact_id=f.id, fact_type=f.fact_type,
            fact_key=f.fact_key, fact_value=f.fact_value,
            normalized_value=f.normalized_value,
        )
        for f in facts
    ]
    result_items = [
        ExperimentResultItem(
            result_id=r.id, result_type=r.result_type,
            name=r.name, experiment_key=r.experiment_key,
        )
        for r in results
    ]
    metric_items = [
        MetricItem(
            metric_id=m.id, name=m.name,
            normalized_name=m.normalized_name,
            value_numeric=m.value_numeric,
            value_text=m.value_text,
            unit=m.unit, split=m.split, direction=m.direction,
        )
        for m in metrics
    ]
    return fact_items, result_items, metric_items


def _load_citation_candidates(
    db: Session,
    *,
    report_id: uuid.UUID,
    max_items: int,
) -> list[CitationCandidate]:
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
        return []
    claims = list(db.execute(
        select(Claim).where(Claim.citation_run_id == run.id)
    ).scalars().all())
    if not claims:
        return []
    claim_ids = [c.id for c in claims]
    ccs = list(db.execute(
        select(ClaimCitation).where(
            ClaimCitation.claim_id.in_(claim_ids)
        )
    ).scalars().all())
    if not ccs:
        return []
    identity_ids = {cc.citation_id for cc in ccs}
    idents = list(db.execute(
        select(CitationIdentity).where(
            CitationIdentity.id.in_(identity_ids)
        ).order_by(CitationIdentity.id.asc()).limit(max_items)
    ).scalars().all())
    return [
        CitationCandidate(
            identity_id=i.id,
            source_id=i.source_id,
            display_label=i.display_label,
        )
        for i in idents
    ]


def build_evidence_packet(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    section,
    max_evidence: int,
    max_technical: int,
) -> EvidencePacket:
    packet = EvidencePacket(
        section_key=section.section_key,
        section_type=section.section_type,
        display_order=section.display_order,
        title=section.title,
        research_objective=section.research_objective,
    )
    packet.m28_items = _load_m28_evidence(
        db,
        manuscript_version_id=manuscript_version_id,
        manuscript_section_id=section.id,
        max_items=max_evidence,
    )
    facts, results, metrics = _load_technical_intelligence(
        db, project_id=project_id, max_items=max_technical,
    )
    packet.technical_facts = facts
    packet.experiment_results = results
    packet.metrics = metrics
    packet.citation_candidates = _load_citation_candidates(
        db, report_id=report_id, max_items=max_technical,
    )
    return packet


__all__ = [
    "EvidenceItem",
    "TechnicalFactItem",
    "ExperimentResultItem",
    "MetricItem",
    "CitationCandidate",
    "EvidencePacket",
    "build_evidence_packet",
]
