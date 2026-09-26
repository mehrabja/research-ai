"""M30 — Real claim→evidence relevance scoring.

No blanket mapping. No constant scores.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.experiment_result import ExperimentResult
from app.db.models.metric import Metric
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.db.models.technical_fact import TechnicalFact
from app.domain.citation import (
    EvidenceType,
    SupportLevel,
    is_supporting,
    normalize_text,
)
from app.services.citation.claims import ExtractedClaim

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _tokens(s: str) -> set[str]:
    if not s:
        return set()
    out: set[str] = set()
    for t in _TOKEN_RE.findall(normalize_text(s).casefold()):
        if len(t) >= 3:
            out.add(t)
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass
class MappedEvidence:
    evidence_type: str
    evidence_id: uuid.UUID
    source_id: uuid.UUID | None
    support_level: str
    relevance_score: float
    provenance: dict


def _classify_support(
    score: float, *, contradictions: bool,
) -> str:
    settings = get_settings()
    support_t = float(settings.citation_support_threshold)
    partial_t = float(settings.citation_partial_threshold)

    if contradictions:
        return SupportLevel.CONTRADICTS.value
    if score >= support_t:
        return SupportLevel.SUPPORTS.value
    if score >= partial_t:
        return SupportLevel.PARTIALLY_SUPPORTS.value
    return SupportLevel.CONTEXT_ONLY.value


def _candidate_m28(
    db: Session, *, claim: ExtractedClaim,
) -> list[tuple[SectionResearchEvidence, str]]:
    if claim.manuscript_section_id is None:
        return []
    rows = list(db.execute(
        select(SectionResearchEvidence)
        .join(
            SectionResearchRun,
            SectionResearchEvidence.research_run_id
            == SectionResearchRun.id,
        )
        .where(
            SectionResearchRun.manuscript_section_id
            == claim.manuscript_section_id,
            SectionResearchRun.status == "completed",
        )
        .order_by(SectionResearchEvidence.rank.asc())
    ).scalars().all())
    out: list[tuple[SectionResearchEvidence, str]] = []
    for e in rows:
        out.append((e, e.excerpt or ""))
    return out


def _candidate_m29(
    db: Session, *, m29_run_id: uuid.UUID | None,
) -> tuple[
    list[tuple[TechnicalFact, str]],
    list[tuple[ExperimentResult, str]],
    list[tuple[Metric, str]],
]:
    if m29_run_id is None:
        return [], [], []
    facts = list(db.execute(
        select(TechnicalFact).where(
            TechnicalFact.technical_intelligence_run_id == m29_run_id,
            TechnicalFact.status.in_(("extracted", "validated")),
        )
    ).scalars().all())
    results = list(db.execute(
        select(ExperimentResult).where(
            ExperimentResult.technical_intelligence_run_id == m29_run_id,
            ExperimentResult.status.in_(("parsed", "validated")),
        )
    ).scalars().all())
    metrics = list(db.execute(
        select(Metric).where(
            Metric.technical_intelligence_run_id == m29_run_id,
            Metric.status.in_(("parsed", "validated")),
        )
    ).scalars().all())

    f_txt = [(f, f"{f.fact_key} {f.fact_value or ''}") for f in facts]
    r_txt = [(r, r"{r.name}") for r in results]
    m_txt = [
        (m, f"{m.normalized_name} {m.value_text or ''}") for m in metrics
    ]
    return f_txt, r_txt, m_txt


def map_evidence_for_claim(
    db: Session,
    *,
    claim: ExtractedClaim,
    project_id: uuid.UUID,
    m29_run_id: uuid.UUID | None,
) -> list[MappedEvidence]:
    settings = get_settings()
    max_ev = int(settings.citation_max_evidence_per_claim)
    claim_tokens = _tokens(claim.claim_text)
    out: list[MappedEvidence] = []

    # --- M28 evidence ---
    for e, text in _candidate_m28(db, claim=claim):
        score = _jaccard(claim_tokens, _tokens(text))
        if score <= 0:
            continue
        level = _classify_support(score, contradictions=False)
        out.append(MappedEvidence(
            evidence_type=EvidenceType.M28_EVIDENCE.value,
            evidence_id=e.id,
            source_id=e.source_id,
            support_level=level,
            relevance_score=min(1.0, score),
            provenance={
                "evidence_type": EvidenceType.M28_EVIDENCE.value,
                "section_research_run_id": str(e.research_run_id),
                "chunk_id": str(e.chunk_id) if e.chunk_id else None,
                "rank": e.rank,
                "m30_version": "m30.1",
            },
        ))

    # --- M29 evidence ---
    f_list, r_list, m_list = _candidate_m29(db, m29_run_id=m29_run_id)
    for f, text in f_list:
        score = _jaccard(claim_tokens, _tokens(text))
        if score <= 0:
            continue
        level = _classify_support(score, contradictions=False)
        out.append(MappedEvidence(
            evidence_type=EvidenceType.M29_TECHNICAL_FACT.value,
            evidence_id=f.id,
            source_id=None,
            support_level=level,
            relevance_score=min(1.0, score),
            provenance={
                "evidence_type": EvidenceType.M29_TECHNICAL_FACT.value,
                "fact_type": f.fact_type,
                "fact_key": f.fact_key,
                "m29_run_id": str(f.technical_intelligence_run_id),
                "context_hash": f.context_hash,
                "m29_version": "m29.1",
                "m30_version": "m30.1",
            },
        ))
    for r, text in r_list:
        score = _jaccard(claim_tokens, _tokens(text))
        if score <= 0:
            continue
        level = _classify_support(score, contradictions=False)
        out.append(MappedEvidence(
            evidence_type=EvidenceType.M29_EXPERIMENT_RESULT.value,
            evidence_id=r.id,
            source_id=None,
            support_level=level,
            relevance_score=min(1.0, score),
            provenance={
                "evidence_type":
                    EvidenceType.M29_EXPERIMENT_RESULT.value,
                "result_type": r.result_type,
                "experiment_key": r.experiment_key,
                "m29_run_id": str(r.technical_intelligence_run_id),
                "context_hash": r.context_hash,
                "m29_version": "m29.1",
                "m30_version": "m30.1",
            },
        ))
    for m, text in m_list:
        score = _jaccard(claim_tokens, _tokens(text))
        if score <= 0:
            continue
        level = _classify_support(score, contradictions=False)
        out.append(MappedEvidence(
            evidence_type=EvidenceType.M29_METRIC.value,
            evidence_id=m.id,
            source_id=None,
            support_level=level,
            relevance_score=min(1.0, score),
            provenance={
                "evidence_type": EvidenceType.M29_METRIC.value,
                "experiment_result_id": str(m.experiment_result_id),
                "normalized_name": m.normalized_name,
                "m29_run_id": str(m.technical_intelligence_run_id),
                "context_hash": m.context_hash,
                "m29_version": "m29.1",
                "m30_version": "m30.1",
            },
        ))

    # Sort by score DESC, deterministic tie-break
    out.sort(key=lambda x: (-x.relevance_score, str(x.evidence_id)))
    _ = is_supporting  # reserved
    _ = project_id
    return out[:max_ev]


__all__ = ["MappedEvidence", "map_evidence_for_claim"]
