"""M28.5 — Manuscript prose Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ManuscriptProseGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    base_manuscript_version_id: uuid.UUID
    mode: str | None = None
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class ManuscriptProseGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    context_hash: str | None = None
    section_count: int | None = None
    word_count: int | None = None


class ManuscriptProseRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID
    base_manuscript_version_id: uuid.UUID
    output_manuscript_version_id: uuid.UUID | None
    research_plan_id: uuid.UUID | None
    section_research_run_id: uuid.UUID | None
    technical_intelligence_run_id: uuid.UUID | None
    citation_run_id: uuid.UUID | None
    context_hash: str
    prose_version: str
    prompt_version: str
    generation_mode: str
    provider: str | None
    model: str | None
    status: str
    section_count: int
    paragraph_count: int
    sentence_count: int
    word_count: int
    warnings: list[Any] | None
    errors: list[Any] | None
    error_message: str | None
    duration_ms: int | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ManuscriptProseSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    run_id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    manuscript_section_id: uuid.UUID | None
    section_key: str
    section_type: str
    display_order: int
    title: str
    status: str
    text: str
    char_start: int
    char_end: int
    word_count: int
    paragraph_count: int
    sentence_count: int
    section_context_hash: str
    provenance: dict[str, Any] | None
    warnings: list[Any] | None
    error_message: str | None
    created_at: datetime


class ManuscriptProseCurrentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run: ManuscriptProseRunRead
    sections: list[ManuscriptProseSectionRead] = Field(
        default_factory=list,
    )


class ManuscriptProseRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ManuscriptProseRunRead]
    total: int
    limit: int
    offset: int


class ManuscriptProseSectionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ManuscriptProseSectionRead]
    total: int
    limit: int
    offset: int


class ManuscriptProseValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ManuscriptProseSectionRegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    manuscript_version_id: uuid.UUID
    section_id: uuid.UUID
    mode: str | None = None
    force: bool = True
    async_: bool = Field(default=True, alias="async")


class ManuscriptProseFinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID
    note: str | None = None
