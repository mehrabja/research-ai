import pytest

from app.core.exceptions import ResearchPlanBudgetInvalid
from app.services.research_planning import budget


def test_allocations_sum_to_one():
    b = budget.build_default_budget(
        section_weights={"a": 0.2, "b": 0.3, "c": 0.5}
    )
    assert abs(sum(b["section_allocations"].values()) - 1.0) < 1e-9


def test_negative_rejected():
    with pytest.raises(ResearchPlanBudgetInvalid):
        budget.normalize_section_allocations({"a": -0.1})


def test_validate_roundtrip():
    b = budget.build_default_budget(
        section_weights={"a": 1, "b": 1, "c": 1}
    )
    budget.validate_budget(b)


def test_invalid_missing_field():
    with pytest.raises(ResearchPlanBudgetInvalid):
        budget.validate_budget({"max_sources": 1})


def test_zero_total_rejected():
    with pytest.raises(ResearchPlanBudgetInvalid):
        budget.normalize_section_allocations({"a": 0, "b": 0})
