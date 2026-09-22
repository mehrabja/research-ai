"""M24 — Research Planning domain primitives (pure)."""
from __future__ import annotations

from enum import StrEnum

RESEARCH_PLAN_VERSION = "m24-v1"
RESEARCH_PLAN_TEMPLATE_VERSION = "m24-template-v1"
RESEARCH_PLAN_COVERAGE_MODEL_VERSION = "m24-cov-v1"
RESEARCH_PLAN_REFERENCE_YEAR = 2026


class ResearchPlanStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    SUPERSEDED = "superseded"
    FAILED = "failed"
    ARCHIVED = "archived"


class PlanningMode(StrEnum):
    DETERMINISTIC = "deterministic"
    HYBRID = "hybrid"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


class ValidationStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


class ResearchPlanRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SectionType(StrEnum):
    TITLE = "title"
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    BACKGROUND = "background"
    RELATED_WORK = "related_work"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    LIMITATIONS = "limitations"
    CONCLUSION = "conclusion"
    FUTURE_WORK = "future_work"
    APPENDIX = "appendix"
    CUSTOM = "custom"


class EvidenceRequirementType(StrEnum):
    BACKGROUND = "background"
    THEORY = "theory"
    METHODOLOGY = "methodology"
    PRIMARY_STUDY = "primary_study"
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"
    GUIDELINE = "guideline"
    DATASET = "dataset"
    BENCHMARK = "benchmark"
    COMPARATIVE = "comparative"
    RECENT_EVIDENCE = "recent_evidence"
    LIMITATION = "limitation"
    COUNTER_EVIDENCE = "counter_evidence"
    SYNTHESIS = "synthesis"
    PROTOCOL = "protocol"


class DependencyType(StrEnum):
    REQUIRES = "requires"
    INFORMS = "informs"
    PRECEDES = "precedes"


RESEARCH_PLAN_STATUSES = tuple(s.value for s in ResearchPlanStatus)
RESEARCH_PLAN_MODES = tuple(m.value for m in PlanningMode)
RESEARCH_PLAN_VALIDATION_STATUSES = tuple(v.value for v in ValidationStatus)
RESEARCH_PLAN_RUN_STATUSES = tuple(s.value for s in ResearchPlanRunStatus)
RESEARCH_PLAN_SECTION_TYPES = tuple(t.value for t in SectionType)
RESEARCH_EVIDENCE_REQUIREMENT_TYPES = tuple(
    t.value for t in EvidenceRequirementType
)
RESEARCH_PLAN_DEPENDENCY_TYPES = tuple(d.value for d in DependencyType)

RESEARCH_PLAN_EVENT_TYPES: tuple[str, ...] = (
    "research_plan_generation_started",
    "research_plan_generation_completed",
    "research_plan_generation_failed",
    "research_plan_generation_skipped",
)
