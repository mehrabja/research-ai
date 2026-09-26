"""M28 — Section Research domain primitives (pure)."""
from __future__ import annotations

from enum import StrEnum

SECTION_RESEARCH_VERSION = "m28-v1"
SECTION_RESEARCH_QUERY_VERSION = "m28-query-v1"
SECTION_RESEARCH_CONTRACT_VERSION = "m28-contract-v1"
SECTION_RESEARCH_CONTEXT_VERSION = "m28-context-v1"
SECTION_RESEARCH_COVERAGE_VERSION = "m28-coverage-v1"

SUPPORTED_CONTRACT_INTENT_MAPPING_VERSIONS: frozenset[str] = frozenset(
    {"m27-intent-v1"}
)


class SectionResearchRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RequirementStatus(StrEnum):
    SATISFIED = "satisfied"
    PARTIALLY_SATISFIED = "partially_satisfied"
    UNSATISFIED = "unsatisfied"
    NOT_APPLICABLE = "not_applicable"


class CoverageState(StrEnum):
    COVERED = "covered"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


SECTION_RESEARCH_RUN_STATUSES = tuple(
    s.value for s in SectionResearchRunStatus
)
REQUIREMENT_STATUSES = tuple(s.value for s in RequirementStatus)
COVERAGE_STATES = tuple(s.value for s in CoverageState)

# Deterministic per-intent query keyword. Values cover all 12 M26
# RetrievalIntent values. Kept in sync with domain/retrieval_advanced.
INTENT_QUERY_KEYWORD: dict[str, str] = {
    "background": "background context",
    "definition": "definition",
    "methodology": "methodology",
    "empirical_evidence": "empirical evidence",
    "comparison": "comparison",
    "causal_evidence": "causal evidence",
    "recent_evidence": "recent evidence",
    "counter_evidence": "counter evidence",
    "limitation": "limitations",
    "gap": "research gap",
    "synthesis": "synthesis",
    "citation": "citations",
}


__all__ = [
    "SECTION_RESEARCH_VERSION",
    "SECTION_RESEARCH_QUERY_VERSION",
    "SECTION_RESEARCH_CONTRACT_VERSION",
    "SECTION_RESEARCH_CONTEXT_VERSION",
    "SECTION_RESEARCH_COVERAGE_VERSION",
    "SUPPORTED_CONTRACT_INTENT_MAPPING_VERSIONS",
    "SectionResearchRunStatus",
    "RequirementStatus",
    "CoverageState",
    "SECTION_RESEARCH_RUN_STATUSES",
    "REQUIREMENT_STATUSES",
    "COVERAGE_STATES",
    "INTENT_QUERY_KEYWORD",
]
