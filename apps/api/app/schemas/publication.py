"""M33 — Publication target + compliance Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PublicationTargetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_code: str = Field(min_length=1, max_length=200)
    profile_version: str = Field(min_length=1, max_length=50)
    venue: str = Field(min_length=1, max_length=500)
    venue_type: str
    citation_style: str
    publisher: str | None = None
    paper_types: list[Any] | None = None
    formatting_rules: dict[str, Any] | None = None
    section_rules: dict[str, Any] | None = None
    word_limits: dict[str, Any] | None = None
    abstract_limits: dict[str, Any] | None = None
    keyword_rules: dict[str, Any] | None = None
    author_rules: dict[str, Any] | None = None
    anonymity_rules: dict[str, Any] | None = None
    figure_table_rules: dict[str, Any] | None = None
    supplementary_rules: dict[str, Any] | None = None
    reference_rules: dict[str, Any] | None = None
    submission_checklist: list[Any] | None = None
    provenance: dict[str, Any] | None = None


class PublicationTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    target_code: str
    profile_version: str
    publisher: str | None
    venue: str
    venue_type: str
    citation_style: str
    active: bool
    profile_schema_version: str
    effective_from: datetime | None
    effective_to: datetime | None
    created_at: datetime
    updated_at: datetime


class PublicationTargetListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[PublicationTargetRead]
    total: int
    limit: int
    offset: int


class PublicationTargetSelectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_id: uuid.UUID
    selection_note: str | None = None


class PublicationTargetSelectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    report_id: uuid.UUID
    target_id: uuid.UUID
    selected_by: uuid.UUID | None
    selection_note: str | None
    created_at: datetime


class PublicationComplianceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    manuscript_version_id: uuid.UUID
    target_id: uuid.UUID
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class PublicationComplianceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    context_hash: str | None = None
    gate: str | None = None
    finding_count: int | None = None
    blocking_count: int | None = None


class PublicationComplianceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID | None
    manuscript_version_id: uuid.UUID
    target_id: uuid.UUID
    context_hash: str
    m33_version: str
    rules_version: str
    target_profile_version: str
    status: str
    finding_count: int
    blocking_count: int
    error_count: int
    warning_count: int
    info_count: int
    gate: str | None
    checklist_state: dict[str, Any] | None
    formatting_summary: dict[str, Any] | None
    warnings: list[Any] | None
    error_message: str | None
    duration_ms: int | None
    created_at: datetime
    completed_at: datetime | None


class PublicationComplianceCurrentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run: PublicationComplianceRunRead


class PublicationComplianceRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[PublicationComplianceRunRead]
    total: int
    limit: int
    offset: int


class PublicationComplianceFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    compliance_run_id: uuid.UUID
    rule_id: str
    category: str
    severity: str
    title: str
    message: str
    location: dict[str, Any] | None
    evidence: dict[str, Any] | None
    remediation: dict[str, Any] | None
    created_at: datetime


class PublicationComplianceFindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[PublicationComplianceFindingRead]
    total: int
    limit: int
    offset: int


class PublicationChecklistRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID
    target_id: uuid.UUID
    target_profile_version: str
    gate: str | None
    checklist_state: dict[str, Any] | None


class PublicationComplianceValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    gate: str | None = None
