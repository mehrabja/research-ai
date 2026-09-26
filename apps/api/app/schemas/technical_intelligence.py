"""M29 — Technical Intelligence Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TechnicalIntelligenceGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class TechnicalIntelligenceGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    context_hash: str | None = None
    fact_count: int | None = None
    result_count: int | None = None
    metric_count: int | None = None


class TechnicalFactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    technical_intelligence_run_id: uuid.UUID
    project_id: uuid.UUID
    project_file_id: uuid.UUID
    code_analysis_id: uuid.UUID | None
    data_profile_id: uuid.UUID | None
    fact_type: str
    fact_key: str
    fact_value: str | None
    normalized_value: str | None
    unit: str | None
    confidence: float
    status: str
    created_at: datetime


class ExperimentResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    technical_intelligence_run_id: uuid.UUID
    project_id: uuid.UUID
    project_file_id: uuid.UUID
    technical_fact_id: uuid.UUID | None
    result_type: str
    name: str
    description: str | None
    value: dict[str, Any] | None
    unit: str | None
    experiment_key: str | None
    status: str
    created_at: datetime


class MetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    technical_intelligence_run_id: uuid.UUID
    project_id: uuid.UUID
    experiment_result_id: uuid.UUID
    name: str
    normalized_name: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    split: str | None
    direction: str | None
    baseline_value: float | None
    delta_value: float | None
    is_primary: bool
    status: str
    created_at: datetime


class TechnicalIntelligenceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID | None
    context_hash: str
    m29_version: str
    status: str
    fact_count: int
    result_count: int
    metric_count: int
    warnings: list[Any] | None
    error_message: str | None
    duration_ms: int | None
    created_at: datetime
    completed_at: datetime | None


class TechnicalIntelligenceCurrentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run: TechnicalIntelligenceRunRead
    fact_count: int
    result_count: int
    metric_count: int


class TechnicalIntelligenceRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[TechnicalIntelligenceRunRead]
    total: int
    limit: int
    offset: int


class TechnicalFactListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[TechnicalFactRead]
    total: int
    limit: int
    offset: int


class ExperimentResultListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ExperimentResultRead]
    total: int
    limit: int
    offset: int


class MetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[MetricRead]
    total: int
    limit: int
    offset: int


class TechnicalIntelligenceValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
