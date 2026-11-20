"""M35 — Orchestration Pydantic schemas."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_OUTPUT_PREVIEW_MAX_BYTES = 16_000
_OUTPUT_PREVIEW_BUDGET_CHARS = 2_800
_OUTPUT_PREVIEW_MAX_DEPTH = 5
_OUTPUT_PREVIEW_MAX_ITEMS = 24
_OUTPUT_PREVIEW_MAX_STRING_CHARS = 900
_OUTPUT_PREVIEW_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "access_token",
        "refresh_token",
        "authorization",
        "password",
        "secret",
        "credential",
        "credentials",
        "private_key",
        "cookie",
        "set_cookie",
    }
)


def _preview_key_is_sensitive(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9_]+", "_", key.casefold()).strip("_")
    return (
        normalized.startswith("_")
        or normalized in _OUTPUT_PREVIEW_SENSITIVE_KEYS
        or any(
            marker in normalized
            for marker in (
                "api_key",
                "access_token",
                "refresh_token",
                "password",
                "secret",
            )
        )
    )


def _preview_value(value: Any, *, depth: int, budget: list[int]) -> Any:
    if budget[0] <= 0:
        return "[preview truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        budget[0] -= 8
        return value
    if isinstance(value, str):
        limit = min(_OUTPUT_PREVIEW_MAX_STRING_CHARS, budget[0])
        clipped = value[:limit]
        budget[0] -= len(clipped)
        return clipped + ("…[truncated]" if len(value) > limit else "")
    if depth >= _OUTPUT_PREVIEW_MAX_DEPTH:
        return "[nested content omitted]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (raw_key, item) in enumerate(value.items()):
            if index >= _OUTPUT_PREVIEW_MAX_ITEMS or budget[0] <= 0:
                result["preview_truncated"] = True
                break
            if not isinstance(raw_key, str) or _preview_key_is_sensitive(raw_key):
                continue
            key = raw_key[:80]
            budget[0] -= len(key)
            result[key] = _preview_value(
                item, depth=depth + 1, budget=budget
            )
        return result
    if isinstance(value, (list, tuple)):
        preview_items = [
            _preview_value(item, depth=depth + 1, budget=budget)
            for item in value[:_OUTPUT_PREVIEW_MAX_ITEMS]
        ]
        if len(value) > _OUTPUT_PREVIEW_MAX_ITEMS:
            preview_items.append("[additional items omitted]")
        return preview_items
    return f"[unsupported value: {type(value).__name__}]"


def build_orchestration_output_preview(
    snapshot: Any,
) -> dict[str, Any] | None:
    """Return a bounded, secret-filtered projection of a persisted node output.

    Raw output_snapshot remains server-side. Only this sanitized preview is
    returned by the report-authorized orchestration read endpoints.
    """
    if not isinstance(snapshot, dict) or not snapshot:
        return None
    safe = _preview_value(
        snapshot,
        depth=0,
        budget=[_OUTPUT_PREVIEW_BUDGET_CHARS],
    )
    if not isinstance(safe, dict):
        return None
    encoded = json.dumps(
        safe, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) > _OUTPUT_PREVIEW_MAX_BYTES:
        return {
            "preview_truncated": True,
            "message": "Node output is too large for an inline preview.",
        }
    return safe


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
    output_preview: dict[str, Any] | None = None
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
