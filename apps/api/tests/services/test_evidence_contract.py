from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.schemas.evidence import EvidenceRecord
from app.services.evidence_contract import (
    from_chunk,
    from_claim_evidence,
    from_section_research,
    from_technical_fact,
)


def test_section_research_adapter_preserves_retrieval_provenance() -> None:
    evidence_id = uuid.uuid4()
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    row = SimpleNamespace(
        id=evidence_id,
        source_id=source_id,
        chunk_id=chunk_id,
        excerpt="supporting excerpt",
        final_score=0.81,
        evidence_role="primary",
        research_run_id=uuid.uuid4(),
        retrieval_stage="hybrid",
        retrieval_reason=["semantic_match"],
        matched_requirement_keys=["rq-1"],
        rank=1,
        created_at=None,
    )

    out = from_section_research(row)

    assert isinstance(out, EvidenceRecord)
    assert out.evidence_key == f"m28_evidence:{evidence_id}"
    assert out.source_id == source_id
    assert out.chunk_id == chunk_id
    assert out.text == "supporting excerpt"
    assert out.score == 0.81
    assert out.provenance["origin"] == "section_research"
    assert out.provenance["rank"] == 1


def test_claim_evidence_adapter_uses_underlying_kind() -> None:
    evidence_id = uuid.uuid4()
    claim_id = uuid.uuid4()
    row = SimpleNamespace(
        id=uuid.uuid4(),
        claim_id=claim_id,
        evidence_type="m29_metric",
        evidence_id=evidence_id,
        source_id=None,
        support_level="supports",
        relevance_score=0.63,
        provenance={"metric": "accuracy"},
        created_at=None,
    )

    out = from_claim_evidence(row)

    assert out.kind == "m29_metric"
    assert out.evidence_id == evidence_id
    assert out.claim_id == claim_id
    assert out.support_level == "supports"
    assert out.score == 0.63
    assert out.provenance["origin"] == "claim_evidence"
    assert out.provenance["underlying_evidence_id"] == str(evidence_id)


def test_chunk_adapter_keeps_precise_locator() -> None:
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    row = SimpleNamespace(
        id=chunk_id,
        source_id=source_id,
        content="chunk text",
        page_number=7,
        char_start=100,
        char_end=180,
        chunk_index=3,
        embedding_status="completed",
        embedding_model_version="v1",
        created_at=None,
    )

    out = from_chunk(row)

    assert out.kind == "retrieval_chunk"
    assert out.source_id == source_id
    assert out.chunk_id == chunk_id
    assert out.locator.page_number == 7
    assert out.locator.char_start == 100
    assert out.locator.char_end == 180


def test_technical_fact_adapter_keeps_file_provenance() -> None:
    project_file_id = uuid.uuid4()
    row = SimpleNamespace(
        id=uuid.uuid4(),
        project_file_id=project_file_id,
        fact_key="learning_rate",
        fact_value="0.001",
        normalized_value="0.001",
        unit=None,
        confidence=0.92,
        fact_type="configuration",
        provenance={"line": 14},
        created_at=None,
    )

    out = from_technical_fact(row)

    assert out.kind == "m29_technical_fact"
    assert out.project_file_id == project_file_id
    assert out.title == "learning_rate"
    assert out.text == "0.001"
    assert out.score == 0.92
    assert out.provenance["line"] == 14
