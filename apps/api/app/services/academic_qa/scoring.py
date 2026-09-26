"""M31 — Dimension-level and composite QA scoring."""
from __future__ import annotations

from typing import Any

from app.domain.academic_qa import (
    QA_DIMENSIONS,
    SEVERITY_WEIGHTS,
    QASeverity,
)
from app.services.academic_qa.findings import QAFinding


def _score_for_findings(
    findings: list[QAFinding],
) -> tuple[float, dict[str, int]]:
    """Deterministic per-dimension score in [0, 1]."""
    counts = {
        QASeverity.INFO.value: 0,
        QASeverity.WARNING.value: 0,
        QASeverity.ERROR.value: 0,
        QASeverity.BLOCKING.value: 0,
    }
    penalty = 0.0
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
        penalty += SEVERITY_WEIGHTS.get(f.severity, 0.0)
    score = max(0.0, 1.0 - penalty)
    return score, counts


# Maps finding category -> dimension key
_CATEGORY_TO_DIM: dict[str, str] = {
    "citation_integrity": "citation_integrity",
    "evidence_coverage": "evidence_coverage",
    "claim_quality": "evidence_coverage",
    "structural_consistency": "structural_integrity",
    "numerical_consistency": "numerical_consistency",
    "methodology": "methodology_completeness",
    "terminology": "terminology_consistency",
    "reproducibility": "reproducibility",
    "academic_style": "academic_style",
}


def compute_dimension_scores(
    findings: list[QAFinding],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[QAFinding]] = {d: [] for d in QA_DIMENSIONS}
    for f in findings:
        dim = _CATEGORY_TO_DIM.get(f.category)
        if dim:
            grouped.setdefault(dim, []).append(f)

    out: dict[str, dict[str, Any]] = {}
    for dim, items in grouped.items():
        score, counts = _score_for_findings(items)
        out[dim] = {
            "value": round(score, 4),
            "calculation_method": "severity_weighted_v1",
            "input_counts": counts,
            "findings": len(items),
        }
    return out


def compute_composite(
    dimension_scores: dict[str, dict[str, Any]],
) -> float:
    if not dimension_scores:
        return 0.0
    vals = [d["value"] for d in dimension_scores.values()]
    return round(sum(vals) / len(vals), 4)


__all__ = ["compute_dimension_scores", "compute_composite"]
