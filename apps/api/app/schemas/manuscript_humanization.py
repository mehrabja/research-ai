"""M32 — Manuscript humanization Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ManuscriptHumanizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    manuscript_version_id: uuid.UUID
    mode: str = "academic"
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class ManuscriptHumanizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    context_hash: str | None = None
    gate: str | None = None


class HumanizationIterationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    humanization_run_id: uuid.UUID
    iteration_index: int
    detection_score_mean: float | None
    preservation_result: dict[str, Any] | None
    qa_impact: dict[str, Any] | None
    accepted: bool | None


class HumanizationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID | None
    manuscript_version_id: uuid.UUID | None
    stage: str
    language: str
    status: str
    mode: str | None
    m32_version: str | None
    context_hash: str | None
    gate: str | None
    preservation_summary: dict[str, Any] | None
    cost_usd: float | None
    tokens_used: int | None
    created_at: datetime
    completed_at: datetime | None


class ManuscriptHumanizationCurrentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run: HumanizationRunRead


class HumanizationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[HumanizationRunRead]
    total: int
    limit: int
    offset: int


class HumanizationIterationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[HumanizationIterationRead]
    total: int
    limit: int
    offset: int


class ManuscriptHumanizationValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    gate: str | None = None
