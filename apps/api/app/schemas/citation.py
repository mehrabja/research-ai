"""M30 — Citation Engine Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CitationGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    manuscript_version_id: uuid.UUID
    citation_style: str = "author_year"
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class CitationGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    context_hash: str | None = None
    claim_count: int | None = None
    citation_count: int | None = None
    unsupported_count: int | None = None
    coverage_score: float | None = None


class CitationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID | None
    manuscript_version_id: uuid.UUID
    context_hash: str
    m30_version: str
    citation_style: str
    status: str
    claim_count: int
    citation_count: int
    unsupported_count: int
    mixed_support_count: int
    duplicate_reference_count: int
    coverage_score: float
    warnings: list[Any] | None
    error_message: str | None
    duration_ms: int | None
    created_at: datetime
    completed_at: datetime | None


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    citation_run_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    manuscript_section_id: uuid.UUID | None
    claim_hash: str
    claim_text: str
    claim_type: str
    status: str
    created_at: datetime


class ClaimEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    claim_id: uuid.UUID
    evidence_type: str
    evidence_id: uuid.UUID
    source_id: uuid.UUID | None
    support_level: str
    relevance_score: float
    provenance: dict[str, Any]


class ClaimCitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    claim_id: uuid.UUID
    citation_id: uuid.UUID
    relation_type: str
    support_level: str
    relevance_score: float
    paragraph_index: int | None
    sentence_index: int | None
    char_start: int | None
    char_end: int | None
    citation_order: int | None


class CitationIdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    report_id: uuid.UUID
    source_id: uuid.UUID
    canonical_doi: str | None
    canonical_title: str | None
    canonical_first_year: int | None = Field(
        default=None,
        validation_alias="canonical_year",
    )
    display_label: str | None


class CitationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CitationRunRead]
    total: int
    limit: int
    offset: int


class CitationCurrentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run: CitationRunRead
    claims: list[ClaimRead] = Field(default_factory=list)


class BibliographyEntryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    citation_id: str
    source_id: str
    label: str
    rendered: str
    order: int
    display_key: str


class BibliographyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: str
    entries: list[BibliographyEntryRead]
    unresolved_identity_ids: list[str] = Field(default_factory=list)


class CitationValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidenceMatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: ClaimRead
    evidence: list[ClaimEvidenceRead] = Field(default_factory=list)
    citations: list[ClaimCitationRead] = Field(default_factory=list)


class EvidenceMatrixRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_id: uuid.UUID
    citation_run_id: uuid.UUID
    rows: list[EvidenceMatrixRow] = Field(default_factory=list)
