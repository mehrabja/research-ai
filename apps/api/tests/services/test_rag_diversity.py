import uuid

from app.services.rag.candidates import Candidate
from app.services.rag.diversity import apply_mmr
from app.services.rag.scoring import ScoredCandidate


def _sc(source_id, score):
    c = Candidate(
        chunk_id=uuid.uuid4(),
        source_id=source_id,
        report_id=uuid.uuid4(),
        chunk_index=0,
        vector_distance=None,
        vector_rank=None,
        lexical_score=None,
        lexical_rank=None,
        fusion_score=score,
        stage="hybrid",
    )
    return ScoredCandidate(candidate=c, final_score=score)


def test_mmr_prefers_new_sources():
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    scored = [_sc(s1, 0.9), _sc(s1, 0.85), _sc(s2, 0.5)]
    out = apply_mmr(scored, lambda_=0.5, max_results=2)
    assert len(out) == 2
    assert {o.candidate.source_id for o in out} == {s1, s2}


def test_mmr_bounded_by_max_results():
    scored = [_sc(uuid.uuid4(), 0.9 - i * 0.1) for i in range(5)]
    out = apply_mmr(scored, lambda_=0.5, max_results=3)
    assert len(out) == 3


def test_mmr_empty():
    assert apply_mmr([], lambda_=0.5, max_results=5) == []
