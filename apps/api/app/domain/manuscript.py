"""M27 — Manuscript Architecture domain primitives (pure)."""
from __future__ import annotations

from enum import StrEnum

MANUSCRIPT_ARCHITECTURE_VERSION = "m27-v1"
MANUSCRIPT_TEMPLATE_VERSION = "m27-template-v1"
MANUSCRIPT_COVERAGE_MODEL_VERSION = "m27-coverage-v1"
MANUSCRIPT_INTENT_MAPPING_VERSION = "m27-intent-v1"

MANUSCRIPT_TITLE_MAX_CHARS = 240


class ManuscriptStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    SUPERSEDED = "superseded"
    FAILED = "failed"
    ARCHIVED = "archived"


class ManuscriptVersionStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class ManuscriptRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ManuscriptDependencyType(StrEnum):
    REQUIRES = "requires"
    INFORMS = "informs"
    PRECEDES = "precedes"


MANUSCRIPT_STATUSES = tuple(s.value for s in ManuscriptStatus)
MANUSCRIPT_VERSION_STATUSES = tuple(s.value for s in ManuscriptVersionStatus)
MANUSCRIPT_RUN_STATUSES = tuple(s.value for s in ManuscriptRunStatus)
MANUSCRIPT_DEPENDENCY_TYPES = tuple(d.value for d in ManuscriptDependencyType)

_INTENT_MAP: dict[str, tuple[str, ...]] = {
    "background": ("background",),
    "theory": ("definition", "background"),
    "methodology": ("methodology",),
    "primary_study": ("empirical_evidence",),
    "systematic_review": ("synthesis",),
    "meta_analysis": ("synthesis",),
    "guideline": ("methodology",),
    "dataset": ("empirical_evidence",),
    "benchmark": ("comparison",),
    "comparative": ("comparison",),
    "recent_evidence": ("recent_evidence",),
    "limitation": ("limitation",),
    "counter_evidence": ("counter_evidence",),
    "synthesis": ("synthesis",),
    "protocol": ("methodology",),
}

KNOWN_RETRIEVAL_INTENTS: frozenset[str] = frozenset({
    "background", "definition", "methodology", "empirical_evidence",
    "comparison", "causal_evidence", "recent_evidence",
    "counter_evidence", "limitation", "gap", "synthesis", "citation",
})

CITATION_POLICY_BY_SECTION_TYPE: dict[str, bool] = {
    "introduction": True,
    "background": True,
    "related_work": True,
    "methods": True,
    "results": True,
    "discussion": True,
    "limitations": True,
    "conclusion": True,
    "future_work": False,
    "appendix": False,
    "title": False,
    "abstract": False,
    "custom": False,
}


def map_requirement_type_to_intents(req_type: str) -> tuple[str, ...]:
    return _INTENT_MAP.get(req_type, ())


def citation_required_for(
    section_type: str, has_required_evidence: bool
) -> bool:
    default = CITATION_POLICY_BY_SECTION_TYPE.get(section_type, False)
    if section_type == "conclusion":
        return bool(has_required_evidence)
    return default


__all__ = [
    "MANUSCRIPT_ARCHITECTURE_VERSION",
    "MANUSCRIPT_TEMPLATE_VERSION",
    "MANUSCRIPT_COVERAGE_MODEL_VERSION",
    "MANUSCRIPT_INTENT_MAPPING_VERSION",
    "MANUSCRIPT_TITLE_MAX_CHARS",
    "ManuscriptStatus",
    "ManuscriptVersionStatus",
    "ManuscriptRunStatus",
    "ManuscriptDependencyType",
    "MANUSCRIPT_STATUSES",
    "MANUSCRIPT_VERSION_STATUSES",
    "MANUSCRIPT_RUN_STATUSES",
    "MANUSCRIPT_DEPENDENCY_TYPES",
    "KNOWN_RETRIEVAL_INTENTS",
    "CITATION_POLICY_BY_SECTION_TYPE",
    "map_requirement_type_to_intents",
    "citation_required_for",
]
