"""M35 — Orchestration Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrchestrationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    goal: str = Field(min_length=1, max_length=1000)
    strategy: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] | None = None
    force: bool = False
    async_: bool = Field(default=True, alias="async")


class OrchestrationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    context_hash: str | None = None
    node_count: int | None = None
    completed_node_count: int | None = None
    failed_node_count: int | None = None


class OrchestrationNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    run_id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    node_key: str
    node_version: str
    node_type: str
    sequence: int
    depends_on: list[Any] | None
    status: str
    attempt: int
    max_attempts: int
    deterministic: bool
    error_class: str | None
    error_message: str | None
    duration_ms: int | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class OrchestrationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    user_id: uuid.UUID | None
    goal: str
    context_hash: str
    orchestration_version: str
    planner_version: str
    tool_registry_version: str
    strategy: str
    status: str
    current_node_key: str | None
    budget: dict[str, Any]
    budget_used: dict[str, Any] | None
    approvals_required: list[Any] | None
    approvals_received: list[Any] | None
    summary: dict[str, Any] | None
    errors: list[Any] | None
    checkpoint_state: dict[str, Any] | None
    last_checkpoint_at: datetime | None
    node_count: int
    completed_node_count: int
    failed_node_count: int
    error_message: str | None
    duration_ms: int | None
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime


class OrchestrationRunDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run: OrchestrationRunRead
    nodes: list[OrchestrationNodeRead] = Field(default_factory=list)


class OrchestrationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[OrchestrationRunRead]
    total: int
    limit: int
    offset: int


class OrchestrationNodeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[OrchestrationNodeRead]
    total: int
    limit: int
    offset: int


class OrchestrationPauseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    run_id: uuid.UUID


class OrchestrationCancelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    run_id: uuid.UUID


class OrchestrationToolRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    version: str
    description: str
    permission: str
    deterministic: bool


class OrchestrationToolListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[OrchestrationToolRead]


class OrchestrationValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OrchestrationStrategyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    description: str


class OrchestrationStrategyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[OrchestrationStrategyRead] = Field(default_factory=list)


class OrchestrationApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    run_id: uuid.UUID
    node_id: uuid.UUID


class OrchestrationResumeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    run_id: uuid.UUID
