"""M28.5 — Manuscript prose generation domain primitives."""
from __future__ import annotations

from enum import StrEnum

M28_5_VERSION = "m28.5.1"
PROSE_PROMPT_VERSION = "m28.5-prompt-v1"
PROSE_SECTION_CONTRACT_VERSION = "m28.5-contract-v1"


class ProseGenerationMode(StrEnum):
    DETERMINISTIC = "deterministic"
    PROVIDER_ASSISTED = "provider_assisted"
    HYBRID = "hybrid"


class ProseRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProseSectionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProseGenerationMode4(StrEnum):
    """Alias kept for symmetry with repository naming."""
    pass


PROSE_GENERATION_MODES = tuple(m.value for m in ProseGenerationMode)
PROSE_RUN_STATUSES = tuple(s.value for s in ProseRunStatus)
PROSE_SECTION_STATUSES = tuple(s.value for s in ProseSectionStatus)

# Sections that receive special handling.
SPECIAL_SECTIONS = frozenset({
    "abstract", "introduction", "conclusion", "future_work",
})

# Evidence strength tiers. Ordered weakest → strongest.
EVIDENCE_TIERS: tuple[str, ...] = (
    "context_only",
    "partial",
    "direct",
)

# Default per-run caps. Overridable via Settings.
DEFAULT_PROSE_LIMITS: dict[str, int] = {
    "max_sections": 30,
    "max_paragraphs_per_section": 20,
    "max_sentences_per_paragraph": 15,
    "max_manuscript_words": 30000,
    "max_evidence_per_section": 30,
    "max_technical_facts_per_section": 30,
}


def is_special_section(section_key: str) -> bool:
    return section_key in SPECIAL_SECTIONS


def weakest_tier(*tiers: str | None) -> str:
    """Deterministic weakest-of. Missing inputs treated as context_only."""
    cleaned = [t for t in tiers if t]
    if not cleaned:
        return "context_only"
    for t in EVIDENCE_TIERS:
        if t in cleaned:
            return t
    return "context_only"


__all__ = [
    "M28_5_VERSION",
    "PROSE_PROMPT_VERSION",
    "PROSE_SECTION_CONTRACT_VERSION",
    "ProseGenerationMode",
    "ProseRunStatus",
    "ProseSectionStatus",
    "PROSE_GENERATION_MODES",
    "PROSE_RUN_STATUSES",
    "PROSE_SECTION_STATUSES",
    "SPECIAL_SECTIONS",
    "EVIDENCE_TIERS",
    "DEFAULT_PROSE_LIMITS",
    "is_special_section",
    "weakest_tier",
]
