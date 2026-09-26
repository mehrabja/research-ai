"""M21/M22 — Classification schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ClassificationSourceLiteral = Literal[
    "explicit", "inferred", "user_override"
]
ClassificationMethodLiteral = Literal["explicit", "heuristic", "llm"]
ClassificationStatusLiteral = Literal[
    "pending", "completed", "needs_review", "failed"
]
ClassificationRunStatusLiteral = Literal[
    "completed", "needs_review", "failed", "skipped"
]


class _Alternative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = None
    name: str | None = None
    confidence: float | None = None


class _DomainSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None
    name: str | None
    confidence: float | None
    source: ClassificationSourceLiteral | None
    method: ClassificationMethodLiteral | None
    reason: str | None
    alternatives: list[_Alternative]


class _PaperTypeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None
    confidence: float | None
    source: ClassificationSourceLiteral | None
    method: ClassificationMethodLiteral | None
    reason: str | None
    secondary: list[str]
    alternatives: list[_Alternative]


class _ResearchDesignSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None
    confidence: float | None
    source: ClassificationSourceLiteral | None
    method: ClassificationMethodLiteral | None
    reason: str | None
    alternatives: list[_Alternative]


class ClassificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    domain: _DomainSummary
    paper_type: _PaperTypeSummary
    research_design: _ResearchDesignSummary
    status: ClassificationStatusLiteral
    needs_review: bool
    error_message: str | None
    classifier_version: str
    taxonomy_version: str
    context_meta: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class EvidenceItemRead(BaseModel):
    model_config = ConfigDict(
        extra="forbid", from_attributes=True
    )
    id: uuid.UUID
    target: str
    signal_type: str
    source_location: str
    matched_text: str
    weight: float
    target_code: str | None


class EvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[EvidenceItemRead]
    total: int
    limit: int
    offset: int


class ClassificationOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain_code: str | None = Field(default=None, max_length=200)
    paper_type_code: str | None = Field(default=None, max_length=200)
    research_design_code: str | None = Field(default=None, max_length=200)


# --- M22: history + explanation -------------------------------------


class ClassificationRunRead(BaseModel):
    """Immutable run record (one row per classification execution)."""
    model_config = ConfigDict(
        extra="forbid", from_attributes=True
    )

    id: uuid.UUID
    project_id: uuid.UUID
    classification_id: uuid.UUID | None
    context_hash: str | None
    classifier_version: str
    taxonomy_version: str
    status: ClassificationRunStatusLiteral
    domain_code: str | None
    paper_type_code: str | None
    research_design_code: str | None
    confidence_summary: dict[str, Any] | None
    explanation: dict[str, Any] | None
    error_message: str | None
    duration_ms: int | None
    created_at: datetime


class ClassificationHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ClassificationRunRead]
    total: int
    limit: int
    offset: int


class ClassificationExplanationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification_id: uuid.UUID | None
    context_hash: str | None
    status: str
    created_at: datetime | None
    explanation: dict[str, Any] | None
