"""Adapters into the canonical evidence contract."""
from __future__ import annotations

from typing import Any

from app.db.models.citation import ClaimEvidence
from app.db.models.experiment_result import ExperimentResult
from app.db.models.metric import Metric
from app.db.models.section_research import SectionResearchEvidence
from app.db.models.source import Chunk
from app.db.models.technical_fact import TechnicalFact
from app.schemas.evidence import EvidenceKind, EvidenceLocator, EvidenceRecord


def _key(kind: EvidenceKind, evidence_id: Any) -> str:
    return f"{kind}:{evidence_id}"


def _record(
    *,
    kind: EvidenceKind,
    evidence_id: Any,
    claim_id: Any = None,
    source_id: Any = None,
    chunk_id: Any = None,
    project_file_id: Any = None,
    title: str | None = None,
    text: str | None = None,
    score: float | None = None,
    support_level: str | None = None,
    locator: EvidenceLocator | None = None,
    provenance: dict[str, Any] | None = None,
    created_at: Any = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_key=_key(kind, evidence_id),
        evidence_id=evidence_id,
        kind=kind,
        claim_id=claim_id,
        source_id=source_id,
        chunk_id=chunk_id,
        project_file_id=project_file_id,
        title=title,
        text=text,
        score=score,
        support_level=support_level,
        locator=locator or EvidenceLocator(),
        provenance=provenance or {},
        created_at=created_at,
    )


def from_section_research(evidence: SectionResearchEvidence) -> EvidenceRecord:
    return _record(
        kind="m28_evidence",
        evidence_id=evidence.id,
        source_id=evidence.source_id,
        chunk_id=evidence.chunk_id,
        text=evidence.excerpt,
        score=float(evidence.final_score),
        support_level=evidence.evidence_role,
        provenance={
            "origin": "section_research",
            "research_run_id": str(evidence.research_run_id),
            "retrieval_stage": evidence.retrieval_stage,
            "retrieval_reason": list(evidence.retrieval_reason or []),
            "matched_requirement_keys": list(
                evidence.matched_requirement_keys or []
            ),
            "rank": evidence.rank,
        },
        created_at=evidence.created_at,
    )


def from_claim_evidence(evidence: ClaimEvidence) -> EvidenceRecord:
    provenance = dict(evidence.provenance or {})
    provenance["origin"] = "claim_evidence"
    provenance["evidence_type"] = evidence.evidence_type
    provenance["underlying_evidence_id"] = str(evidence.evidence_id)
    kind: EvidenceKind = (
        evidence.evidence_type
        if evidence.evidence_type in {
            "m28_evidence",
            "m29_technical_fact",
            "m29_experiment_result",
            "m29_metric",
        }
        else "claim_evidence"
    )
    return _record(
        kind=kind,
        evidence_id=evidence.evidence_id,
        claim_id=evidence.claim_id,
        source_id=evidence.source_id,
        score=float(evidence.relevance_score),
        support_level=evidence.support_level,
        provenance=provenance,
        created_at=evidence.created_at,
    )


def from_chunk(chunk: Chunk) -> EvidenceRecord:
    return _record(
        kind="retrieval_chunk",
        evidence_id=chunk.id,
        source_id=chunk.source_id,
        chunk_id=chunk.id,
        text=chunk.content,
        locator=EvidenceLocator(
            page_number=chunk.page_number,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        ),
        provenance={
            "origin": "chunk",
            "chunk_index": chunk.chunk_index,
            "embedding_status": chunk.embedding_status,
            "embedding_model_version": chunk.embedding_model_version,
        },
        created_at=chunk.created_at,
    )


def from_technical_fact(fact: TechnicalFact) -> EvidenceRecord:
    return _record(
        kind="m29_technical_fact",
        evidence_id=fact.id,
        project_file_id=fact.project_file_id,
        title=fact.fact_key,
        text=fact.fact_value,
        score=float(fact.confidence),
        support_level="context_only",
        provenance={
            "origin": "technical_fact",
            "fact_type": fact.fact_type,
            "normalized_value": fact.normalized_value,
            "unit": fact.unit,
            **dict(fact.provenance or {}),
        },
        created_at=fact.created_at,
    )


def from_experiment_result(result: ExperimentResult) -> EvidenceRecord:
    return _record(
        kind="m29_experiment_result",
        evidence_id=result.id,
        project_file_id=result.project_file_id,
        title=result.name,
        text=result.description,
        support_level="context_only",
        provenance={
            "origin": "experiment_result",
            "result_type": result.result_type,
            "experiment_key": result.experiment_key,
            "value": result.value,
            "unit": result.unit,
            **dict(result.provenance or {}),
        },
        created_at=result.created_at,
    )


def from_metric(metric: Metric) -> EvidenceRecord:
    value = (
        str(metric.value_numeric)
        if metric.value_numeric is not None
        else metric.value_text
    )
    return _record(
        kind="m29_metric",
        evidence_id=metric.id,
        title=metric.normalized_name,
        text=value,
        support_level="context_only",
        provenance={
            "origin": "metric",
            "name": metric.name,
            "normalized_name": metric.normalized_name,
            "unit": metric.unit,
            "split": metric.split,
            "direction": metric.direction,
            "baseline_value": metric.baseline_value,
            "delta_value": metric.delta_value,
            "experiment_result_id": str(metric.experiment_result_id),
            **dict(metric.provenance or {}),
        },
        created_at=metric.created_at,
    )
