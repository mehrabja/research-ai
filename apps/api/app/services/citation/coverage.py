"""M30 — Coverage metrics."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CoverageReport:
    claim_count: int
    supported_claim_count: int
    supported_with_source_count: int
    supported_without_source_count: int
    partially_supported_claim_count: int
    unsupported_claim_count: int
    contradicted_claim_count: int
    citation_count: int
    citation_density: float
    duplicate_reference_count: int
    coverage_score: float


def compute_coverage(
    *,
    claim_count: int,
    supported_with_source_count: int,
    supported_without_source_count: int,
    partially_supported_claim_count: int,
    unsupported_claim_count: int,
    contradicted_claim_count: int,
    citation_count: int,
    duplicate_reference_count: int,
) -> CoverageReport:
    supported = (
        supported_with_source_count + supported_without_source_count
    )
    density = citation_count / claim_count if claim_count > 0 else 0.0
    coverage = supported / claim_count if claim_count > 0 else 0.0
    return CoverageReport(
        claim_count=claim_count,
        supported_claim_count=supported,
        supported_with_source_count=supported_with_source_count,
        supported_without_source_count=supported_without_source_count,
        partially_supported_claim_count=partially_supported_claim_count,
        unsupported_claim_count=unsupported_claim_count,
        contradicted_claim_count=contradicted_claim_count,
        citation_count=citation_count,
        citation_density=density,
        duplicate_reference_count=duplicate_reference_count,
        coverage_score=coverage,
    )


__all__ = ["CoverageReport", "compute_coverage"]
