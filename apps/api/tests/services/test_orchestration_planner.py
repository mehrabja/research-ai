"""M35 orchestration planner tests."""
from __future__ import annotations

import pytest

from app.services.orchestration.planner import (
    available_orchestration_strategies,
    plan_orchestration,
)
from app.services.orchestration.registry import list_tools


def test_research_pipeline_contains_full_preparation_flow() -> None:
    plan = plan_orchestration(
        goal="prepare submission",
        strategy="research_pipeline",
        payload={},
        max_nodes=20,
    )
    assert plan.node_keys() == [
        "build_plan",
        "manuscript_generate",
        "technical_intelligence",
        "manuscript_prose_generate",
        "generate_citations",
        "academic_qa",
        "humanize",
        "target_compliance",
    ]


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown orchestration strategy"):
        plan_orchestration(
            goal="x",
            strategy="not-a-real-strategy",
            payload=None,
            max_nodes=10,
        )


def test_strategy_catalog_matches_presets() -> None:
    keys = [key for key, _description in available_orchestration_strategies()]
    assert "research_pipeline" in keys
    assert "complete_pre_submission" in keys
    assert "roundtable_review" in keys


def test_resolve_qa_blockers_has_unique_node_keys() -> None:
    plan = plan_orchestration(
        goal="resolve quality blockers",
        strategy="resolve_qa_blockers",
        payload={},
        max_nodes=20,
    )
    assert len(plan.node_keys()) == len(set(plan.node_keys()))


def test_all_planner_nodes_exist_in_tool_registry() -> None:
    catalog = {
        key
        for key, _description in available_orchestration_strategies()
    }
    assert catalog
    plans = set()
    for strategy in catalog:
        plans.update(
            plan_orchestration(
                goal="audit",
                strategy=strategy,
                payload={},
                max_nodes=50,
            ).node_keys()
        )
    registered = set(list_tools())
    assert plans <= registered
