"""M28 — Per-requirement + section coverage evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.section_research import (
    SECTION_RESEARCH_COVERAGE_VERSION,
    CoverageState,
    RequirementStatus,
)
from app.services.section_research.evidence import RequirementMatch


@dataclass(frozen=True)
class RequirementCoverage:
    requirement_key: str
    status: str
    matched_source_count: int
    matched_evidence_count: int
    coverage_score: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement_key": self.requirement_key,
            "status": self.status,
            "matched_source_count": int(self.matched_source_count),
            "matched_evidence_count": int(self.matched_evidence_count),
            "coverage_score": float(self.coverage_score),
            "reason": self.reason,
        }


@dataclass
class SectionCoverage:
    coverage_version: str
    coverage_target: float
    coverage_score: float
    coverage_state: str
    per_requirement: list[RequirementCoverage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "coverage_version": self.coverage_version,
            "coverage_target": float(self.coverage_target),
            "coverage_score": float(self.coverage_score),
            "coverage_state": self.coverage_state,
            "per_requirement": [r.as_dict() for r in self.per_requirement],
            "warnings": list(self.warnings),
        }


def _score_for_requirement(
    *, required: bool, matched_sources: int, min_sources: int | None,
) -> tuple[str, float, str]:
    if not required and matched_sources == 0:
        return (
            RequirementStatus.NOT_APPLICABLE.value, 0.0,
            "not_required_and_no_match",
        )
    if matched_sources == 0:
        return (
            RequirementStatus.UNSATISFIED.value, 0.0,
            "no_sources_matched",
        )
    if min_sources is None or min_sources <= 0:
        return (
            RequirementStatus.SATISFIED.value, 1.0,
            "any_match_no_min",
        )
    if matched_sources >= min_sources:
        return (
            RequirementStatus.SATISFIED.value, 1.0,
            f"met_min_sources_{matched_sources}_of_{min_sources}",
        )
    score = matched_sources / min_sources
    return (
        RequirementStatus.PARTIALLY_SATISFIED.value,
        round(score, 4),
        f"partial_{matched_sources}_of_{min_sources}",
    )


def evaluate_requirement_coverage(
    *,
    requirement: dict[str, Any],
    match: RequirementMatch | None,
) -> RequirementCoverage:
    rk = requirement["requirement_key"]
    required = bool(requirement.get("required", False))
    min_sources = requirement.get("min_sources")
    if not isinstance(min_sources, int):
        min_sources = None

    m_sources = match.distinct_sources if match else 0
    m_chunks = match.matching_chunks if match else 0

    status, score, reason = _score_for_requirement(
        required=required,
        matched_sources=m_sources,
        min_sources=min_sources,
    )
    return RequirementCoverage(
        requirement_key=rk,
        status=status,
        matched_source_count=m_sources,
        matched_evidence_count=m_chunks,
        coverage_score=score,
        reason=reason,
    )


def evaluate_section_coverage(
    *,
    requirements: tuple[dict[str, Any], ...],
    matches: dict[str, RequirementMatch],
    coverage_target: float,
    covered_threshold: float = 0.7,
    partial_threshold: float = 0.4,
) -> SectionCoverage:
    per_req = [
        evaluate_requirement_coverage(
            requirement=r, match=matches.get(r["requirement_key"]),
        )
        for r in requirements
    ]

    # Weighted score over required requirements only.
    weighted_num = 0.0
    weighted_den = 0.0
    for r, cov in zip(requirements, per_req, strict=True):
        if not bool(r.get("required", False)):
            continue
        w = float(r.get("coverage_weight", 1.0) or 1.0)
        if w <= 0:
            continue
        weighted_num += w * float(cov.coverage_score)
        weighted_den += w

    section_score = (
        weighted_num / weighted_den if weighted_den > 0 else 0.0
    )

    if not requirements or weighted_den == 0 or section_score >= covered_threshold:
        state = CoverageState.COVERED.value
    elif section_score >= partial_threshold:
        state = CoverageState.PARTIAL.value
    else:
        state = CoverageState.INSUFFICIENT.value

    warnings: list[str] = []
    if section_score < coverage_target:
        warnings.append(
            f"coverage_below_target:{section_score:.3f}<{coverage_target:.3f}"
        )

    return SectionCoverage(
        coverage_version=SECTION_RESEARCH_COVERAGE_VERSION,
        coverage_target=float(coverage_target),
        coverage_score=round(section_score, 4),
        coverage_state=state,
        per_requirement=per_req,
        warnings=warnings,
    )


__all__ = [
    "RequirementCoverage",
    "SectionCoverage",
    "evaluate_requirement_coverage",
    "evaluate_section_coverage",
]
