"""M31 — Academic QA Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AcademicQAGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    manuscript_version_id: uuid.UUID
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class AcademicQAGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    context_hash: str | None = None
    gate: str | None = None
    finding_count: int | None = None
    blocking_count: int | None = None


class AcademicQAFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    qa_run_id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    manuscript_section_id: uuid.UUID | None
    claim_id: uuid.UUID | None
    citation_id: uuid.UUID | None
    rule_id: str
    category: str
    severity: str
    title: str
    message: str
    classification: str
    confidence: float | None
    status: str
    created_at: datetime


class AcademicQARunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID | None
    manuscript_version_id: uuid.UUID
    context_hash: str
    m31_version: str
    rules_version: str
    status: str
    execution_mode: str
    finding_count: int
    blocking_count: int
    error_count: int
    warning_count: int
    info_count: int
    gate: str | None
    dimension_scores: dict[str, Any] | None
    summary: dict[str, Any] | None
    warnings: list[Any] | None
    error_message: str | None
    duration_ms: int | None
    created_at: datetime
    completed_at: datetime | None


class AcademicQACurrentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run: AcademicQARunRead


class AcademicQARunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AcademicQARunRead]
    total: int
    limit: int
    offset: int


class AcademicQAFindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AcademicQAFindingRead]
    total: int
    limit: int
    offset: int


class AcademicQAValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    gate: str | None = None
