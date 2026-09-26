"""M28 — Query plan + filters tests (no DB)."""
from __future__ import annotations

import pytest

from app.core.exceptions import SectionResearchContractInvalid
from app.services.section_research import filters as f_svc
from app.services.section_research import query as q_svc

# ---------- query plan ----------


def test_build_query_plan_single_query_when_cap_one():
    plan = q_svc.build_query_plan(
        research_objective="Discuss topic X.",
        retrieval_intents=["background"],
        max_queries=1,
    )
    assert plan.primary == "Discuss topic X."
    assert plan.derived == ()
    assert plan.all_queries() == ("Discuss topic X.",)


def test_build_query_plan_primary_plus_derived():
    plan = q_svc.build_query_plan(
        research_objective="Discuss topic X.",
        retrieval_intents=["background", "recent_evidence", "synthesis"],
        max_queries=3,
    )
    assert plan.primary == "Discuss topic X."
    assert len(plan.derived) == 2
    assert plan.derived[0] == "background context: Discuss topic X."
    assert plan.derived[1] == "recent evidence: Discuss topic X."
    assert plan.all_queries() == (
        "Discuss topic X.",
        "background context: Discuss topic X.",
        "recent evidence: Discuss topic X.",
    )


def test_build_query_plan_is_deterministic():
    args = {
        "research_objective": "Objective.",
        "retrieval_intents": [
            "background", "synthesis", "limitation",
        ],
        "max_queries": 4,
    }
    p1 = q_svc.build_query_plan(**args)
    p2 = q_svc.build_query_plan(**args)
    assert p1.all_queries() == p2.all_queries()


def test_build_query_plan_deduplicates_intents():
    plan = q_svc.build_query_plan(
        research_objective="Obj.",
        retrieval_intents=["background", "background", "limitation"],
        max_queries=5,
    )
    assert plan.derived == (
        "background context: Obj.",
        "limitations: Obj.",
    )


def test_build_query_plan_caps_derived():
    plan = q_svc.build_query_plan(
        research_objective="Obj.",
        retrieval_intents=[
            "background", "recent_evidence", "synthesis",
            "limitation", "comparison", "methodology",
        ],
        max_queries=3,
    )
    assert len(plan.derived) == 2


def test_build_query_plan_rejects_empty_objective():
    with pytest.raises(SectionResearchContractInvalid):
        q_svc.build_query_plan(
            research_objective="",
            retrieval_intents=["background"],
            max_queries=3,
        )


def test_build_query_plan_skips_unknown_intents_gracefully():
    plan = q_svc.build_query_plan(
        research_objective="Obj.",
        retrieval_intents=["background", "made_up"],
        max_queries=5,
    )
    assert plan.derived == ("background context: Obj.",)


def test_build_query_plan_normalizes_whitespace():
    plan = q_svc.build_query_plan(
        research_objective="  Discuss\n\t topic   X.  ",
        retrieval_intents=[],
        max_queries=1,
    )
    assert plan.primary == "Discuss topic X."


# ---------- filters ----------


def test_build_effective_filters_empty_constraints():
    f, w = f_svc.build_effective_filters(source_constraints={})
    assert f.min_year is None
    assert f.max_year is None
    assert f.required_full_text is False
    assert f.allowed_source_ids == ()
    assert f.preferred_paper_types == ()
    assert f.preferred_research_designs == ()
    assert f.min_relevance_score is None
    assert w == []


def test_build_effective_filters_with_max_age():
    f, _ = f_svc.build_effective_filters(
        source_constraints={"max_age_years": 5},
        reference_year=2026,
    )
    assert f.min_year == 2021
    assert f.max_year == 2026


def test_build_effective_filters_with_full_text():
    f, _ = f_svc.build_effective_filters(
        source_constraints={"full_text_required": True},
    )
    assert f.required_full_text is True


def test_build_effective_filters_preferred_codes():
    f, _ = f_svc.build_effective_filters(
        source_constraints={
            "preferred_paper_types": ["original_research"],
            "preferred_research_designs": ["cohort"],
        },
    )
    assert f.preferred_paper_types == ("original_research",)
    assert f.preferred_research_designs == ("cohort",)


def test_build_effective_filters_invalid_min_relevance():
    f, w = f_svc.build_effective_filters(
        source_constraints={"min_relevance_score": "not-a-float"},
    )
    assert f.min_relevance_score is None
    assert "invalid_min_relevance_score" in w


def test_effective_filters_m26_dict_is_json_serializable():
    import json
    f, _ = f_svc.build_effective_filters(
        source_constraints={"max_age_years": 3, "full_text_required": True},
        reference_year=2026,
    )
    d = f.m26_dict()
    json.dumps(d)  # must not raise
    assert d["min_year"] == 2023
    assert d["max_year"] == 2026
    assert d["required_full_text"] is True
    assert d["allowed_source_ids"] == []
