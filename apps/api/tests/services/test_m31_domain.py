"""M31 — domain primitives."""
from __future__ import annotations

from app.domain.academic_qa import (
    M31_VERSION,
    QA_CATEGORIES,
    QA_DIMENSIONS,
    QAGate,
    compute_gate,
    is_blocking_severity,
)


def test_version() -> None:
    assert M31_VERSION == "m31.1"


def test_categories_cover_required() -> None:
    required = {
        "claim_quality", "citation_integrity", "evidence_coverage",
        "methodology", "numerical_consistency", "structural_consistency",
        "terminology", "reproducibility", "academic_style",
    }
    assert required.issubset(set(QA_CATEGORIES))


def test_dimensions_count() -> None:
    assert len(QA_DIMENSIONS) == 8


def test_compute_gate() -> None:
    assert compute_gate(
        blocking_count=0, error_count=0, warning_count=0,
    ) == QAGate.PASS.value
    assert compute_gate(
        blocking_count=0, error_count=0, warning_count=3,
    ) == QAGate.PASS_WITH_WARNINGS.value
    assert compute_gate(
        blocking_count=0, error_count=1, warning_count=0,
    ) == QAGate.PASS_WITH_WARNINGS.value
    assert compute_gate(
        blocking_count=1, error_count=0, warning_count=0,
    ) == QAGate.BLOCKED.value


def test_is_blocking() -> None:
    assert is_blocking_severity("blocking")
    assert not is_blocking_severity("error")
