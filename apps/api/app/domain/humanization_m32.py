"""M32 — Advanced Humanization domain primitives.

Extends M14. Does not replace it.
"""
from __future__ import annotations

from enum import StrEnum

M32_VERSION = "m32.1"
M32_PRESERVATION_VERSION = "m32-preservation-v1"

# New M14 stage value for M32 runs.
M32_STAGE = "manuscript"


class HumanizationMode(StrEnum):
    CONSERVATIVE = "conservative"
    ACADEMIC = "academic"
    NATURAL_ACADEMIC = "natural_academic"
    JOURNAL_TARGETED = "journal_targeted"


class HumanizationGate(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    REJECTED = "rejected"


class PreservationOutcome(StrEnum):
    OK = "ok"
    DRIFT_DETECTED = "drift_detected"
    INSUFFICIENT_INPUT = "insufficient_input"


HUMANIZATION_MODES = tuple(m.value for m in HumanizationMode)
HUMANIZATION_GATES = tuple(g.value for g in HumanizationGate)
PRESERVATION_OUTCOMES = tuple(o.value for o in PreservationOutcome)

# Deterministic preservation categories. Order matters for report output.
PRESERVATION_CATEGORIES: tuple[str, ...] = (
    "citations",
    "numbers",
    "units",
    "named_entities",
    "technical_terms",
    "equations",
    "section_structure",
    "reference_markers",
)

# How aggressively each mode allows rewriting.
#   max_edit_ratio:     upper bound on changed-char fraction
#   preserve_ratio_min: minimum preservation score to accept iteration
MODE_POLICIES: dict[str, dict[str, float]] = {
    HumanizationMode.CONSERVATIVE.value: {
        "max_edit_ratio": 0.15,
        "preserve_ratio_min": 0.98,
    },
    HumanizationMode.ACADEMIC.value: {
        "max_edit_ratio": 0.25,
        "preserve_ratio_min": 0.95,
    },
    HumanizationMode.NATURAL_ACADEMIC.value: {
        "max_edit_ratio": 0.35,
        "preserve_ratio_min": 0.92,
    },
    HumanizationMode.JOURNAL_TARGETED.value: {
        "max_edit_ratio": 0.30,
        "preserve_ratio_min": 0.95,
    },
}


def mode_policy(mode: str) -> dict[str, float]:
    return MODE_POLICIES.get(
        mode, MODE_POLICIES[HumanizationMode.ACADEMIC.value]
    )


def compute_gate(
    *,
    drift_count: int,
    iteration_accepted: bool,
) -> str:
    """Deterministic gate evaluation."""
    if drift_count > 0 and not iteration_accepted:
        return HumanizationGate.REJECTED.value
    if drift_count > 0:
        return HumanizationGate.PASS_WITH_WARNINGS.value
    return HumanizationGate.PASS.value


__all__ = [
    "M32_VERSION",
    "M32_PRESERVATION_VERSION",
    "M32_STAGE",
    "HumanizationMode",
    "HumanizationGate",
    "PreservationOutcome",
    "HUMANIZATION_MODES",
    "HUMANIZATION_GATES",
    "PRESERVATION_OUTCOMES",
    "PRESERVATION_CATEGORIES",
    "MODE_POLICIES",
    "mode_policy",
    "compute_gate",
]
