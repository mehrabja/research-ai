"""M32 — domain primitives."""
from __future__ import annotations

from app.domain.humanization_m32 import (
    HUMANIZATION_MODES,
    M32_VERSION,
    PRESERVATION_CATEGORIES,
    HumanizationGate,
    HumanizationMode,
    compute_gate,
    mode_policy,
)


def test_version() -> None:
    assert M32_VERSION == "m32.1"


def test_modes_cover_required() -> None:
    required = {
        "conservative", "academic",
        "natural_academic", "journal_targeted",
    }
    assert required == set(HUMANIZATION_MODES)


def test_preservation_categories() -> None:
    assert "citations" in PRESERVATION_CATEGORIES
    assert "numbers" in PRESERVATION_CATEGORIES


def test_mode_policy_defaults() -> None:
    p = mode_policy(HumanizationMode.CONSERVATIVE.value)
    assert p["max_edit_ratio"] < 0.2
    assert p["preserve_ratio_min"] >= 0.95


def test_mode_policy_unknown_falls_back() -> None:
    p = mode_policy("nonsense")
    assert "max_edit_ratio" in p


def test_compute_gate() -> None:
    assert compute_gate(
        drift_count=0, iteration_accepted=True,
    ) == HumanizationGate.PASS.value
    assert compute_gate(
        drift_count=2, iteration_accepted=True,
    ) == HumanizationGate.PASS_WITH_WARNINGS.value
    assert compute_gate(
        drift_count=2, iteration_accepted=False,
    ) == HumanizationGate.REJECTED.value
