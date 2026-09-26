"""M26 — P1 Stage B: coverage + requirement filtering."""
from __future__ import annotations

import uuid
from decimal import Decimal

from app.db.models.literature import ProjectLiteratureItem
from app.db.models.research_plan import ResearchEvidenceRequirement
from app.db.models.source import Source
from app.domain.research_plan import RESEARCH_PLAN_REFERENCE_YEAR
from app.services.rag import coverage as cov_svc
from app.services.rag import plan_filter as pf_svc
from app.services.rag.candidates import Candidate


def _src(*, year: int | None = 2020, status: str = "full_text"):
    s = Source(
        report_id=uuid.uuid4(),
        title="T",
        status=status,
        year=year,
    )
    s.id = uuid.uuid4()
    return s


def _lit(
    source_id: uuid.UUID,
    *,
    paper_type: str | None = "empirical",
    design: str | None = "experimental",
    screening: str = "included",
    relevance: float | None = 0.8,
    methods: str | None = None,
    findings: str | None = None,
    limitations: str | None = None,
    intervention: str | None = None,
    comparator: str | None = None,
):
    lit = ProjectLiteratureItem(
        project_id=uuid.uuid4(),
        source_id=source_id,
        screening_status=screening,
        paper_type_code=paper_type,
        research_design_code=design,
        relevance_score=(
            Decimal(str(relevance)) if relevance is not None else None
        ),
        methods_summary=methods,
        findings_summary=findings,
        limitations_summary=limitations,
        intervention=intervention,
        comparator=comparator,
    )
    lit.id = uuid.uuid4()
    return lit


def _cand(source_id: uuid.UUID, score: float = 0.5):
    return Candidate(
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


def _res(source_id: uuid.UUID, score: float = 0.8, chunk_id=None):
    return {
        "rank": 1,
        "chunk_id": chunk_id or uuid.uuid4(),
        "source_id": source_id,
        "final_score": score,
    }


def _req(**overrides) -> ResearchEvidenceRequirement:
    base = {
        "plan_id": uuid.uuid4(),
        "section_id": uuid.uuid4(),
        "requirement_key": "r1",
        "requirement_type": "primary_study",
        "description": "desc",
        "required": True,
        "priority": 0,
        "full_text_required": False,
        "coverage_weight": Decimal("1"),
    }
    base.update(overrides)
    r = ResearchEvidenceRequirement(**base)
    r.id = uuid.uuid4()
    return r


# ===================================================================== #
# Coverage tests
# ===================================================================== #


def test_coverage_no_results_all_missing():
    out = cov_svc.compute_intent_coverage(
        intents=["background", "methodology"],
        results=[],
        sources_by_id={},
        literature_by_source_id={},
    )
    assert out["satisfied_intents"] == []
    assert sorted(out["missing_intents"]) == ["background", "methodology"]
    assert out["overall_score"] == 0.0


def test_coverage_one_relevant_result_only_matching_satisfied():
    s = _src()
    lit = _lit(s.id, methods="m", findings="f")
    results = [_res(s.id, 0.95)]
    out = cov_svc.compute_intent_coverage(
        intents=["empirical_evidence", "recent_evidence"],
        results=results,
        sources_by_id={s.id: s},
        literature_by_source_id={s.id: lit},
    )
    assert "empirical_evidence" in out["satisfied_intents"]
    assert "recent_evidence" in out["missing_intents"]


def test_coverage_thresholds():
    assert cov_svc.INTENT_COVERAGE_WEAK_THRESHOLD == 0.40
    assert cov_svc.INTENT_COVERAGE_SATISFIED_THRESHOLD == 0.70


def test_coverage_distinct_source_counting():
    s1 = _src()
    s2 = _src()
    results = [_res(s1.id, 0.9), _res(s1.id, 0.8), _res(s2.id, 0.7)]
    out = cov_svc.compute_intent_coverage(
        intents=["background"],
        results=results,
        sources_by_id={s1.id: s1, s2.id: s2},
        literature_by_source_id={},
    )
    details = out["intent_details"]["background"]
    assert details["distinct_sources"] == 2
    assert details["matching_results"] == 3


def test_coverage_comparison_two_chunks_same_source_not_satisfied():
    s = _src()
    results = [_res(s.id, 0.95), _res(s.id, 0.9)]
    out = cov_svc.compute_intent_coverage(
        intents=["comparison"],
        results=results,
        sources_by_id={s.id: s},
        literature_by_source_id={},
    )
    assert "comparison" not in out["satisfied_intents"]


def test_coverage_comparison_two_distinct_sources_can_satisfy():
    s1, s2 = _src(), _src()
    results = [_res(s1.id, 0.9), _res(s2.id, 0.9)]
    out = cov_svc.compute_intent_coverage(
        intents=["comparison"],
        results=results,
        sources_by_id={s1.id: s1, s2.id: s2},
        literature_by_source_id={},
    )
    assert out["intent_details"]["comparison"]["state"] in (
        "satisfied", "weak",
    )


def test_coverage_synthesis_two_chunks_same_source_not_satisfied():
    s = _src()
    results = [_res(s.id, 0.95), _res(s.id, 0.9), _res(s.id, 0.85)]
    out = cov_svc.compute_intent_coverage(
        intents=["synthesis"],
        results=results,
        sources_by_id={s.id: s},
        literature_by_source_id={},
    )
    assert "synthesis" not in out["satisfied_intents"]


def test_coverage_synthesis_two_distinct_sources_can_satisfy():
    s1, s2 = _src(), _src()
    results = [_res(s1.id, 0.9), _res(s2.id, 0.9)]
    out = cov_svc.compute_intent_coverage(
        intents=["synthesis"],
        results=results,
        sources_by_id={s1.id: s1, s2.id: s2},
        literature_by_source_id={},
    )
    assert out["intent_details"]["synthesis"]["state"] in (
        "satisfied", "weak",
    )


def test_coverage_recent_evidence_reference_year():
    s_old = _src(year=RESEARCH_PLAN_REFERENCE_YEAR - 20)
    s_new = _src(year=RESEARCH_PLAN_REFERENCE_YEAR - 1)
    results = [_res(s_old.id, 0.95), _res(s_new.id, 0.95)]
    out = cov_svc.compute_intent_coverage(
        intents=["recent_evidence"],
        results=results,
        sources_by_id={s_old.id: s_old, s_new.id: s_new},
        literature_by_source_id={},
    )
    assert out["intent_details"]["recent_evidence"]["matching_results"] == 1


def test_coverage_missing_source_id_excluded():
    s = _src()
    orphan = uuid.uuid4()
    results = [_res(s.id, 0.95), _res(orphan, 0.99)]
    out = cov_svc.compute_intent_coverage(
        intents=["background"],
        results=results,
        sources_by_id={s.id: s},
        literature_by_source_id={},
    )
    assert out["intent_details"]["background"]["matching_results"] == 1


def test_coverage_deterministic():
    s = _src()
    results = [_res(s.id, 0.8)]
    a = cov_svc.compute_intent_coverage(
        intents=["background", "methodology"],
        results=results,
        sources_by_id={s.id: s},
        literature_by_source_id={},
    )
    b = cov_svc.compute_intent_coverage(
        intents=["background", "methodology"],
        results=results,
        sources_by_id={s.id: s},
        literature_by_source_id={},
    )
    assert a == b


def test_coverage_version_persisted():
    out = cov_svc.compute_intent_coverage(
        intents=[],
        results=[],
        sources_by_id={},
        literature_by_source_id={},
    )
    assert out["coverage_version"] == cov_svc.INTENT_COVERAGE_VERSION


# ===================================================================== #
# Causal evidence semantics
# ===================================================================== #


def test_causal_requires_design_compat_not_only_intervention():
    s = _src()
    lit = _lit(
        s.id,
        design="case_study",
        intervention="drug_x",
        comparator="placebo",
    )
    out = cov_svc.compute_intent_coverage(
        intents=["causal_evidence"],
        results=[_res(s.id, 0.95)],
        sources_by_id={s.id: s},
        literature_by_source_id={s.id: lit},
    )
    assert "causal_evidence" not in out["satisfied_intents"]


def test_causal_design_and_signal_satisfies():
    s = _src()
    lit = _lit(
        s.id,
        design="randomized_controlled_trial",
        intervention="drug_x",
        comparator="placebo",
    )
    out = cov_svc.compute_intent_coverage(
        intents=["causal_evidence"],
        results=[_res(s.id, 0.95)],
        sources_by_id={s.id: s},
        literature_by_source_id={s.id: lit},
    )
    assert "causal_evidence" in out["satisfied_intents"]


def test_causal_missing_signal_not_satisfied():
    s = _src()
    lit = _lit(
        s.id,
        design="randomized_controlled_trial",
        intervention=None,
        comparator=None,
    )
    out = cov_svc.compute_intent_coverage(
        intents=["causal_evidence"],
        results=[_res(s.id, 0.95)],
        sources_by_id={s.id: s},
        literature_by_source_id={s.id: lit},
    )
    assert "causal_evidence" not in out["satisfied_intents"]


# ===================================================================== #
# Counter evidence semantics
# ===================================================================== #


def test_counter_evidence_limitations_only_not_satisfied():
    s = _src()
    lit = _lit(s.id, limitations="small sample size")
    out = cov_svc.compute_intent_coverage(
        intents=["counter_evidence"],
        results=[_res(s.id, 0.95)],
        sources_by_id={s.id: s},
        literature_by_source_id={s.id: lit},
    )
    assert "counter_evidence" not in out["satisfied_intents"]
    reasons = out["intent_details"]["counter_evidence"]["reasons"]
    assert any("no_counter_signal" in r for r in reasons)


# ===================================================================== #
# Gap semantics
# ===================================================================== #


def test_gap_generic_source_result_not_satisfied():
    s = _src()
    out = cov_svc.compute_intent_coverage(
        intents=["gap"],
        results=[_res(s.id, 0.95)],
        sources_by_id={s.id: s},
        literature_by_source_id={},
        graph_context=None,
    )
    assert "gap" not in out["satisfied_intents"]


def test_gap_with_graph_context_can_satisfy():
    s = _src()
    graph_context = {"gap_source_ids": [str(s.id)]}
    out = cov_svc.compute_intent_coverage(
        intents=["gap"],
        results=[_res(s.id, 0.95)],
        sources_by_id={s.id: s},
        literature_by_source_id={},
        graph_context=graph_context,
    )
    assert "gap" in out["satisfied_intents"]


def test_gap_non_source_backed_graph_context_ignored():
    s = _src()
    other = uuid.uuid4()
    graph_context = {"gap_source_ids": [str(other)]}
    out = cov_svc.compute_intent_coverage(
        intents=["gap"],
        results=[_res(s.id, 0.95)],
        sources_by_id={s.id: s},
        literature_by_source_id={},
        graph_context=graph_context,
    )
    assert "gap" not in out["satisfied_intents"]


# ===================================================================== #
# Plan filtering tests
# ===================================================================== #


def test_plan_filter_paper_type():
    s1, s2 = _src(), _src()
    l1 = _lit(s1.id, paper_type="empirical")
    l2 = _lit(s2.id, paper_type="review")
    c1, c2 = _cand(s1.id), _cand(s2.id)
    req = _req(preferred_paper_types=["empirical"])
    r = pf_svc.apply_requirement_filter(
        [c1, c2],
        requirement=req,
        sources_by_id={s1.id: s1, s2.id: s2},
        literature_by_source_id={s1.id: l1, s2.id: l2},
    )
    assert len(r.candidates) == 1
    assert r.candidates[0].source_id == s1.id
    assert r.rejected_counts.get("paper_type") == 1


def test_plan_filter_research_design():
    s1, s2 = _src(), _src()
    l1 = _lit(s1.id, design="experimental")
    l2 = _lit(s2.id, design="case_study")
    c1, c2 = _cand(s1.id), _cand(s2.id)
    req = _req(preferred_research_designs=["experimental"])
    r = pf_svc.apply_requirement_filter(
        [c1, c2],
        requirement=req,
        sources_by_id={s1.id: s1, s2.id: s2},
        literature_by_source_id={s1.id: l1, s2.id: l2},
    )
    assert {c.source_id for c in r.candidates} == {s1.id}
    assert r.rejected_counts.get("research_design") == 1


def test_plan_filter_missing_paper_type_rejected():
    s = _src()
    lit = _lit(s.id, paper_type=None)
    req = _req(preferred_paper_types=["empirical"])
    r = pf_svc.apply_requirement_filter(
        [_cand(s.id)],
        requirement=req,
        sources_by_id={s.id: s},
        literature_by_source_id={s.id: lit},
    )
    assert r.candidates == []
    assert r.rejected_counts.get("paper_type") == 1


def test_plan_filter_max_age_uses_reference_year():
    s_ok = _src(year=RESEARCH_PLAN_REFERENCE_YEAR - 3)
    s_old = _src(year=RESEARCH_PLAN_REFERENCE_YEAR - 30)
    req = _req(max_age_years=5)
    r = pf_svc.apply_requirement_filter(
        [_cand(s_ok.id), _cand(s_old.id)],
        requirement=req,
        sources_by_id={s_ok.id: s_ok, s_old.id: s_old},
        literature_by_source_id={},
    )
    assert {c.source_id for c in r.candidates} == {s_ok.id}
    assert r.rejected_counts.get("max_age") == 1


def test_plan_filter_missing_year_rejected_when_max_age():
    s = _src(year=None)
    req = _req(max_age_years=5)
    r = pf_svc.apply_requirement_filter(
        [_cand(s.id)],
        requirement=req,
        sources_by_id={s.id: s},
        literature_by_source_id={},
    )
    assert r.candidates == []
    assert r.rejected_counts.get("max_age") == 1


def test_plan_filter_full_text_extracted_at():
    s1 = _src(status="abstract_only")
    s1.extracted_at = None
    s2 = _src(status="full_text")
    req = _req(full_text_required=True)
    r = pf_svc.apply_requirement_filter(
        [_cand(s1.id), _cand(s2.id)],
        requirement=req,
        sources_by_id={s1.id: s1, s2.id: s2},
        literature_by_source_id={},
    )
    assert {c.source_id for c in r.candidates} == {s2.id}
    assert r.rejected_counts.get("full_text") == 1


def test_plan_filter_min_relevance():
    s1, s2 = _src(), _src()
    l1 = _lit(s1.id, relevance=0.3)
    l2 = _lit(s2.id, relevance=0.9)
    req = _req(min_relevance_score=Decimal("0.5"))
    r = pf_svc.apply_requirement_filter(
        [_cand(s1.id), _cand(s2.id)],
        requirement=req,
        sources_by_id={s1.id: s1, s2.id: s2},
        literature_by_source_id={s1.id: l1, s2.id: l2},
    )
    assert {c.source_id for c in r.candidates} == {s2.id}
    assert r.rejected_counts.get("min_relevance") == 1


def test_plan_filter_screening_status_excludes():
    s1, s2 = _src(), _src()
    l1 = _lit(s1.id, screening="excluded")
    l2 = _lit(s2.id, screening="included")
    req = _req()
    r = pf_svc.apply_requirement_filter(
        [_cand(s1.id), _cand(s2.id)],
        requirement=req,
        sources_by_id={s1.id: s1, s2.id: s2},
        literature_by_source_id={s1.id: l1, s2.id: l2},
    )
    assert {c.source_id for c in r.candidates} == {s2.id}
    assert r.rejected_counts.get("screening_status") == 1


def test_plan_filter_min_sources_counts_distinct():
    s1, s2 = _src(), _src()
    req = _req(min_sources=3)
    r = pf_svc.apply_requirement_filter(
        [_cand(s1.id), _cand(s1.id), _cand(s2.id)],
        requirement=req,
        sources_by_id={s1.id: s1, s2.id: s2},
        literature_by_source_id={},
    )
    assert len(r.candidates) == 3
    assert r.distinct_source_count == 2
    assert r.min_sources_satisfied is False
    assert any(
        "requirement_min_sources_unsatisfied" in w
        for w in r.warnings
    )


def test_plan_filter_chunk_duplication_does_not_count_sources():
    s = _src()
    cands = [_cand(s.id) for _ in range(10)]
    req = _req(min_sources=3)
    r = pf_svc.apply_requirement_filter(
        cands,
        requirement=req,
        sources_by_id={s.id: s},
        literature_by_source_id={},
    )
    assert r.distinct_source_count == 1
    assert r.min_sources_satisfied is False
