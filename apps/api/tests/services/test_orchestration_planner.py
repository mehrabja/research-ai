"""M35 orchestration planner tests."""
from __future__ import annotations

import pytest

from app.services.orchestration.planner import (
    available_orchestration_strategies,
    plan_orchestration,
)


def test_research_pipeline_contains_full_preparation_flow() -> None:
    plan = plan_orchestration(
        goal="prepare submission",
        strategy="research_pipeline",
        payload={},
        max_nodes=20,
    )
    assert plan.node_keys() == [
        "build_plan",
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
