"""Domain-level generation contracts.

Framework-independent: no SQLAlchemy, FastAPI, HTTP, provider SDKs.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


class GenerationAlreadySucceeded(Exception):
    """Internal control-flow signal. NOT an API error."""


AttemptState = Literal["created", "existing_running", "already_succeeded"]


@dataclass(frozen=True)
class GenerationAttemptLease:
    run: object
    state: AttemptState


class EmptyGenerationError(ValueError):
    """Provider returned empty or whitespace-only text."""


class UnknownEvidenceMarkerError(ValueError):
    """Generated text referenced an evidence marker not in the set."""


@dataclass(frozen=True)
class GenerationProfile:
    provider: str
    model: str
    temperature: float
    max_output_tokens: int
    profile_version: str

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("provider is required")
        if not self.model:
            raise ValueError("model is required")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("temperature must be in [0, 2]")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be > 0")
        if not self.profile_version:
            raise ValueError("profile_version is required")


def build_generation_profile_id(profile: GenerationProfile) -> str:
    return (
        f"{profile.provider}/{profile.model}:"
        f"{profile.temperature:.2f}:{profile.max_output_tokens}:"
        f"{profile.profile_version}"
    )


@dataclass(frozen=True)
class EvidenceItem:
    rank: int
    marker: str
    evidence_id: str
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    content: str
    fusion_score: float


@dataclass(frozen=True)
class EvidenceSet:
    items: tuple[EvidenceItem, ...]

    def marker_map(self) -> dict[str, EvidenceItem]:
        return {it.marker: it for it in self.items}

    def markers(self) -> frozenset[str]:
        return frozenset(it.marker for it in self.items)


@dataclass(frozen=True)
class GenerationContext:
    report_id: uuid.UUID
    job_id: uuid.UUID
    topic: str
    output_language: str
    domain: str | None
    audience_level: str | None
    tone: str | None
    length: str | None
    structure_template: str | None
    system_prompt: str
    user_prompt: str
    evidence: EvidenceSet
    profile: GenerationProfile


@dataclass(frozen=True)
class GenerationProviderResult:
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResult:
    text: str
    language: str
    profile_id: str
    evidence: EvidenceSet
    cited_markers: tuple[str, ...]
    provider_result: GenerationProviderResult


_MARKER_RE = re.compile(r"\[E(\d+)\]")


def extract_citation_markers(text: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for m in _MARKER_RE.finditer(text):
        marker = f"[E{m.group(1)}]"
        seen.setdefault(marker, None)
    return tuple(seen.keys())


def validate_generation_output(
    *, text: str, evidence: EvidenceSet
) -> tuple[str, ...]:
    stripped = text.strip()
    if not stripped:
        raise EmptyGenerationError("provider returned empty text")
    markers = extract_citation_markers(text)
    known = evidence.markers()
    unknown = [m for m in markers if m not in known]
    if unknown:
        raise UnknownEvidenceMarkerError(
            f"generated text references unknown markers: {unknown}"
        )
    return markers


__all__ = [
    "AttemptState",
    "EmptyGenerationError",
    "EvidenceItem",
    "EvidenceSet",
    "GenerationAlreadySucceeded",
    "GenerationAttemptLease",
    "GenerationContext",
    "GenerationProfile",
    "GenerationProviderResult",
    "GenerationResult",
    "UnknownEvidenceMarkerError",
    "build_generation_profile_id",
    "extract_citation_markers",
    "validate_generation_output",
]
