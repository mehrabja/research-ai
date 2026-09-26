import uuid
from decimal import Decimal

from app.db.models.source import Source
from app.services.rag.candidates import Candidate
from app.services.rag.scoring import (
    quality_score_for_source,
    score_candidates,
)


def _c(source_id):
    return Candidate(
        chunk_id=uuid.uuid4(),
        source_id=source_id,
        report_id=uuid.uuid4(),
        chunk_index=0,
        vector_distance=0.1,
        vector_rank=1,
        lexical_score=1.2,
        lexical_rank=1,
        fusion_score=0.5,
        stage="hybrid",
    )


def test_quality_score_full_text():
    s = Source(report_id=uuid.uuid4(), title="T", status="full_text")
    assert quality_score_for_source(s) == 0.85


def test_quality_score_decimal_source_quality():
    s = Source(
        report_id=uuid.uuid4(),
        title="T",
        status="metadata_only",
        source_quality=Decimal("0.77"),
    )
    assert quality_score_for_source(s) == 0.77


def test_score_candidates_deterministic_order():
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    c1, c2 = _c(s1), _c(s2)
    sources = {
        s1: Source(report_id=uuid.uuid4(), title="a", status="full_text"),
        s2: Source(report_id=uuid.uuid4(), title="b", status="metadata_only"),
    }
    out1 = score_candidates([c1, c2], sources_by_id=sources)
    out2 = score_candidates([c2, c1], sources_by_id=sources)
    assert [o.candidate.chunk_id for o in out1] == [
        o.candidate.chunk_id for o in out2
    ]
