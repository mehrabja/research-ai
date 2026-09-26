"""M28 — Evidence + coverage tests (pure, no DB)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.services.section_research import coverage as cov_svc
from app.services.section_research import evidence as ev_svc

# ---------- fakes ----------


@dataclass
class _FakeSource:
    id: uuid.UUID
    year: int | None = 2020
    status: str = "full_text"
    extracted_at: object | None = None
    title: str = "A paper"
    authors: list | None = None
    source_quality: Decimal | None = None


@dataclass
class _FakeLit:
    source_id: uuid.UUID
    screening_status: str = "included"
    paper_type_code: str | None = None
    research_design_code: str | None = None
    relevance_score: Decimal | None = None


def _req(key: str, **overrides) -> dict:
    base = {
        "requirement_id": str(uuid.uuid4()),
        "requirement_key": key,
        "requirement_type": "primary_study",
        "required": True,
        "priority": 5,
        "min_sources": 2,
        "max_sources": None,
        "preferred_paper_types": [],
        "preferred_research_designs": [],
        "max_age_years": None,
        "full_text_required": False,
        "min_relevance_score": None,
        "coverage_weight": 1.0,
        "retrieval_intents": ["empirical_evidence"],
    }
    base.update(overrides)
    return base


def _cand(source_id, chunk_id=None, rank=1, score=0.9):
    return {
        "rank": rank,
        "chunk_id": chunk_id or uuid.uuid4(),
        "source_id": source_id,
        "final_score": score,
        "vector_score": None,
        "lexical_score": None,
        "graph_score": None,
        "memory_score": None,
        "quality_score": None,
        "diversity_penalty": None,
        "retrieval_stage": "hybrid",
        "retrieval_reason": ["hybrid_fusion"],
        "graph_distance": None,
        "memory_match": None,
    }


# ---------- requirement matching ----------


def test_matches_requirement_basic():
    src = _FakeSource(id=uuid.uuid4(), year=2020)
    assert ev_svc.matches_requirement(
        source=src, literature=None, requirement=_req("r1"),
        reference_year=2026,
    )


def test_matches_requirement_rejects_max_age():
    src = _FakeSource(id=uuid.uuid4(), year=2000)
    r = _req("r1", max_age_years=5)
    assert not ev_svc.matches_requirement(
        source=src, literature=None, requirement=r, reference_year=2026,
    )


def test_matches_requirement_rejects_missing_year_for_age_req():
    src = _FakeSource(id=uuid.uuid4(), year=None)
    r = _req("r1", max_age_years=5)
    assert not ev_svc.matches_requirement(
        source=src, literature=None, requirement=r, reference_year=2026,
    )


def test_matches_requirement_rejects_paper_type_mismatch():
    src = _FakeSource(id=uuid.uuid4())
    lit = _FakeLit(source_id=src.id, paper_type_code="systematic_review")
    r = _req("r1", preferred_paper_types=["original_research"])
    assert not ev_svc.matches_requirement(
        source=src, literature=lit, requirement=r, reference_year=2026,
    )


def test_matches_requirement_accepts_paper_type_match():
    src = _FakeSource(id=uuid.uuid4())
    lit = _FakeLit(source_id=src.id, paper_type_code="original_research")
    r = _req("r1", preferred_paper_types=["original_research"])
    assert ev_svc.matches_requirement(
        source=src, literature=lit, requirement=r, reference_year=2026,
    )


def test_matches_requirement_rejects_screening_excluded():
    src = _FakeSource(id=uuid.uuid4())
    lit = _FakeLit(source_id=src.id, screening_status="excluded")
    assert not ev_svc.matches_requirement(
        source=src, literature=lit, requirement=_req("r1"),
        reference_year=2026,
    )


def test_matches_requirement_rejects_full_text_required_but_missing():
    src = _FakeSource(
        id=uuid.uuid4(), status="abstract_only", extracted_at=None,
    )
    r = _req("r1", full_text_required=True)
    assert not ev_svc.matches_requirement(
        source=src, literature=None, requirement=r, reference_year=2026,
    )


def test_matches_requirement_rejects_min_relevance():
    src = _FakeSource(id=uuid.uuid4())
    lit = _FakeLit(source_id=src.id, relevance_score=Decimal("0.3"))
    r = _req("r1", min_relevance_score=0.5)
    assert not ev_svc.matches_requirement(
        source=src, literature=lit, requirement=r, reference_year=2026,
    )


def test_matches_requirement_none_source_rejected():
    assert not ev_svc.matches_requirement(
        source=None, literature=None, requirement=_req("r1"),
        reference_year=2026,
    )


# ---------- evidence selection ----------


def test_select_evidence_basic():
    s1 = uuid.uuid4()
    s2 = uuid.uuid4()
    cands = [_cand(s1, rank=1), _cand(s2, rank=2)]
    sel = ev_svc.select_evidence(
        candidates=cands,
        requirements=(_req("r1", min_sources=1),),
        sources_by_id={
            s1: _FakeSource(id=s1),
            s2: _FakeSource(id=s2),
        },
        literature_by_source_id={},
        chunk_contents={},
        max_evidence=10,
    )
    assert len(sel.selected) == 2
    assert sel.matches["r1"].distinct_sources == 2


def test_select_evidence_respects_max_evidence():
    sources = {uuid.uuid4(): None for _ in range(10)}
    cands = [_cand(sid, rank=i) for i, sid in enumerate(sources)]
    sources_by_id = {sid: _FakeSource(id=sid) for sid in sources}
    sel = ev_svc.select_evidence(
        candidates=cands,
        requirements=(_req("r1", min_sources=1),),
        sources_by_id=sources_by_id,
        literature_by_source_id={},
        chunk_contents={},
        max_evidence=3,
    )
    assert len(sel.selected) == 3


def test_select_evidence_respects_per_source_cap():
    s1 = uuid.uuid4()
    cands = [_cand(s1, rank=i) for i in range(1, 11)]
    sel = ev_svc.select_evidence(
        candidates=cands,
        requirements=(_req("r1", min_sources=1),),
        sources_by_id={s1: _FakeSource(id=s1)},
        literature_by_source_id={},
        chunk_contents={},
        max_evidence=10,
        per_source_cap=2,
    )
    assert len(sel.selected) == 2


def test_select_evidence_drops_unmatched_when_requirements_exist():
    s1 = uuid.uuid4()
    s2 = uuid.uuid4()
    cands = [_cand(s1), _cand(s2)]
    lit = {s1: _FakeLit(
        source_id=s1, paper_type_code="original_research",
    )}
    sel = ev_svc.select_evidence(
        candidates=cands,
        requirements=(_req(
            "r1", min_sources=1,
            preferred_paper_types=["original_research"],
        ),),
        sources_by_id={
            s1: _FakeSource(id=s1),
            s2: _FakeSource(id=s2),
        },
        literature_by_source_id=lit,
        chunk_contents={},
    )
    assert len(sel.selected) == 1
    assert sel.selected[0].source_id == s1
    assert "r1" in sel.selected[0].matched_requirement_keys


def test_select_evidence_keeps_all_when_no_requirements():
    s1 = uuid.uuid4()
    sel = ev_svc.select_evidence(
        candidates=[_cand(s1)],
        requirements=(),
        sources_by_id={s1: _FakeSource(id=s1)},
        literature_by_source_id={},
        chunk_contents={},
    )
    assert len(sel.selected) == 1
    assert sel.selected[0].matched_requirement_keys == ()


def test_select_evidence_marks_unsatisfied_required():
    s1 = uuid.uuid4()
    r = _req(
        "r1", required=True,
        preferred_paper_types=["original_research"],
    )
    lit = {s1: _FakeLit(
        source_id=s1, paper_type_code="systematic_review",
    )}
    sel = ev_svc.select_evidence(
        candidates=[_cand(s1)],
        requirements=(r,),
        sources_by_id={s1: _FakeSource(id=s1)},
        literature_by_source_id=lit,
        chunk_contents={},
    )
    assert any(
        w.startswith("requirement_unsatisfied:r1")
        for w in sel.warnings
    )
    assert sel.selected == []


# ---------- coverage ----------


def test_coverage_satisfied_meets_min_sources():
    r = _req("r1", min_sources=2)
    m = ev_svc.RequirementMatch(
        requirement_key="r1",
        matched_source_ids={uuid.uuid4(), uuid.uuid4()},
    )
    c = cov_svc.evaluate_requirement_coverage(requirement=r, match=m)
    assert c.status == "satisfied"
    assert c.coverage_score == 1.0


def test_coverage_partial_below_min_sources():
    r = _req("r1", min_sources=3)
    m = ev_svc.RequirementMatch(
        requirement_key="r1",
        matched_source_ids={uuid.uuid4()},
    )
    c = cov_svc.evaluate_requirement_coverage(requirement=r, match=m)
    assert c.status == "partially_satisfied"
    assert c.coverage_score < 1.0


def test_coverage_unsatisfied_zero_sources():
    r = _req("r1", required=True, min_sources=2)
    m = ev_svc.RequirementMatch(requirement_key="r1")
    c = cov_svc.evaluate_requirement_coverage(requirement=r, match=m)
    assert c.status == "unsatisfied"


def test_coverage_not_applicable_optional_no_match():
    r = _req("r1", required=False, min_sources=1)
    m = ev_svc.RequirementMatch(requirement_key="r1")
    c = cov_svc.evaluate_requirement_coverage(requirement=r, match=m)
    assert c.status == "not_applicable"


def test_section_coverage_covered():
    r = _req("r1", min_sources=1, coverage_weight=1.0)
    matches = {
        "r1": ev_svc.RequirementMatch(
            requirement_key="r1",
            matched_source_ids={uuid.uuid4()},
        ),
    }
    cov = cov_svc.evaluate_section_coverage(
        requirements=(r,),
        matches=matches,
        coverage_target=0.7,
    )
    assert cov.coverage_state == "covered"
    assert cov.coverage_score == 1.0


def test_section_coverage_insufficient():
    r = _req("r1", min_sources=5, coverage_weight=1.0)
    matches = {"r1": ev_svc.RequirementMatch(requirement_key="r1")}
    cov = cov_svc.evaluate_section_coverage(
        requirements=(r,),
        matches=matches,
        coverage_target=0.7,
    )
    assert cov.coverage_state == "insufficient"
    assert cov.coverage_score == 0.0
    assert any(
        w.startswith("coverage_below_target") for w in cov.warnings
    )


def test_section_coverage_weighted_mix():
    r1 = _req("r1", min_sources=1, coverage_weight=3.0)
    r2 = _req("r2", min_sources=2, coverage_weight=1.0)
    matches = {
        "r1": ev_svc.RequirementMatch(
            requirement_key="r1",
            matched_source_ids={uuid.uuid4()},
        ),
        "r2": ev_svc.RequirementMatch(requirement_key="r2"),
    }
    cov = cov_svc.evaluate_section_coverage(
        requirements=(r1, r2),
        matches=matches,
        coverage_target=0.5,
    )
    # weighted: (3*1 + 1*0) / (3+1) = 0.75
    assert abs(cov.coverage_score - 0.75) < 1e-9
    assert cov.coverage_state == "covered"


def test_section_coverage_ignores_optional():
    r1 = _req("r1", required=True, min_sources=2, coverage_weight=1.0)
    r2 = _req("r2", required=False, min_sources=5, coverage_weight=1.0)
    matches = {
        "r1": ev_svc.RequirementMatch(
            requirement_key="r1",
            matched_source_ids={uuid.uuid4(), uuid.uuid4()},
        ),
        "r2": ev_svc.RequirementMatch(requirement_key="r2"),
    }
    cov = cov_svc.evaluate_section_coverage(
        requirements=(r1, r2),
        matches=matches,
        coverage_target=0.5,
    )
    assert cov.coverage_score == 1.0
    assert cov.coverage_state == "covered"
