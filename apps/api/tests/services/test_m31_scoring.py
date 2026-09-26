"""M31 — scoring tests."""
from __future__ import annotations

from app.services.academic_qa.findings import QAFinding
from app.services.academic_qa.scoring import (
    compute_composite,
    compute_dimension_scores,
)


def _f(cat, sev):
    return QAFinding(
        rule_id=f"r.{cat}.{sev}",
        category=cat, severity=sev,
        title="t", message="m",
    )


def test_empty_scores_are_one() -> None:
    scores = compute_dimension_scores([])
    for v in scores.values():
        assert v["value"] == 1.0


def test_blocking_dominates() -> None:
    scores = compute_dimension_scores([
        _f("citation_integrity", "blocking"),
    ])
    assert scores["citation_integrity"]["value"] == 0.0


def test_warning_lowers_slightly() -> None:
    scores = compute_dimension_scores([
        _f("evidence_coverage", "warning"),
    ])
    assert 0.8 < scores["evidence_coverage"]["value"] < 1.0


def test_composite_of_empty() -> None:
    assert compute_composite({}) == 0.0
