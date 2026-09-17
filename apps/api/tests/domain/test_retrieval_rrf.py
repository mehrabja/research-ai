"""RRF fusion domain tests."""
from __future__ import annotations

import uuid

import pytest

from app.domain.retrieval import (
    RetrievedChunk,
    reciprocal_rank_fusion_score,
)


def test_rrf_basic() -> None:
    score = reciprocal_rank_fusion_score(
        vector_rank=1,
        lexical_rank=1,
        rrf_k=60,
        vector_weight=1.0,
        lexical_weight=1.0,
    )
    assert score == pytest.approx(2 / 61)


def test_rrf_missing_side() -> None:
    score = reciprocal_rank_fusion_score(
        vector_rank=1,
        lexical_rank=None,
        rrf_k=60,
        vector_weight=1.0,
        lexical_weight=1.0,
    )
    assert score == pytest.approx(1 / 61)


def test_rrf_zero_weights_rejected() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion_score(
            vector_rank=1,
            lexical_rank=1,
            rrf_k=60,
            vector_weight=0.0,
            lexical_weight=0.0,
        )


def test_evidence_id_stable() -> None:
    cid = uuid.uuid4()
    sid = uuid.uuid4()
    r = RetrievedChunk(
        chunk_id=cid,
        source_id=sid,
        report_id=uuid.uuid4(),
        chunk_index=0,
        content="x",
        char_start=0,
        char_end=1,
        page_number=None,
        vector_distance=None,
        vector_similarity=None,
        lexical_score=None,
        vector_rank=None,
        lexical_rank=None,
        fusion_score=0.0,
        final_rank=1,
    )
    assert r.evidence_id() == f"source:{sid}:chunk:{cid}"
