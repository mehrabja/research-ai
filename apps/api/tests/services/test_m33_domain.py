"""M33 — domain primitives."""
from __future__ import annotations

from app.domain.publication import (
    CITATION_STYLES,
    COMPLIANCE_CATEGORIES,
    COMPLIANCE_GATES,
    M33_VERSION,
    ComplianceGate,
    compute_gate,
)


def test_version() -> None:
    assert M33_VERSION == "m33.1"


def test_citation_styles() -> None:
    assert "numeric" in CITATION_STYLES
    assert "author_year" in CITATION_STYLES


def test_compliance_categories_cover_required() -> None:
    required = {
        "title", "abstract", "keywords", "section_structure",
        "word_count", "citation_style", "bibliography_style",
        "author_metadata", "anonymization", "figure_table",
        "terminology", "references", "mandatory_declarations",
        "manuscript_completeness",
    }
    assert required.issubset(set(COMPLIANCE_CATEGORIES))


def test_compute_gate() -> None:
    assert compute_gate(
        blocking_count=0, error_count=0, warning_count=0,
    ) == ComplianceGate.PASS.value
    assert compute_gate(
        blocking_count=0, error_count=0, warning_count=2,
    ) == ComplianceGate.PASS_WITH_WARNINGS.value
    assert compute_gate(
        blocking_count=0, error_count=1, warning_count=0,
    ) == ComplianceGate.PASS_WITH_WARNINGS.value
    assert compute_gate(
        blocking_count=1, error_count=0, warning_count=0,
    ) == ComplianceGate.BLOCKED.value


def test_gates_constant() -> None:
    assert set(COMPLIANCE_GATES) == {
        "pass", "pass_with_warnings", "blocked",
    }
