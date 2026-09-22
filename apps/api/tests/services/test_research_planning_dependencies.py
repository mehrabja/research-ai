import pytest

from app.core.exceptions import ResearchPlanDependencyCycle
from app.services.research_planning import dependencies as dep


def test_valid_dag():
    dep.validate_dependency_graph(
        ["a", "b", "c"], [("a", "b"), ("b", "c")]
    )


def test_self_dependency_rejected():
    with pytest.raises(ResearchPlanDependencyCycle):
        dep.validate_dependency_graph(["a"], [("a", "a")])


def test_cycle_rejected():
    with pytest.raises(ResearchPlanDependencyCycle):
        dep.validate_dependency_graph(
            ["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")]
        )


def test_topological_order_deterministic():
    order = dep.topological_order(
        ["a", "b", "c"], [("a", "b"), ("b", "c")]
    )
    assert order == ["a", "b", "c"]
