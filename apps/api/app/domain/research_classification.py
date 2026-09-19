"""M21 — Research classification domain enums (pure)."""
from __future__ import annotations

from enum import StrEnum


class ClassificationSource(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    USER_OVERRIDE = "user_override"


class ClassificationMethod(StrEnum):
    EXPLICIT = "explicit"
    HEURISTIC = "heuristic"
    LLM = "llm"


class ClassificationStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ClassificationTarget(StrEnum):
    DOMAIN = "domain"
    PAPER_TYPE = "paper_type"
    RESEARCH_DESIGN = "research_design"


ALL_SOURCES: tuple[str, ...] = tuple(s.value for s in ClassificationSource)
ALL_METHODS: tuple[str, ...] = tuple(m.value for m in ClassificationMethod)
ALL_STATUSES: tuple[str, ...] = tuple(s.value for s in ClassificationStatus)
ALL_TARGETS: tuple[str, ...] = tuple(t.value for t in ClassificationTarget)


def clamp_confidence(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value
