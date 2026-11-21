"""M40 — bounded Agent Runtime API contracts."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentRuntimeConnectorRead(BaseModel):
    """Catalog metadata; catalog entries are not executable tools."""

    model_config = ConfigDict(extra="forbid")
    id: str
    display_name: str
    category: str
    category_name: str
    description: str
    integration_status: Literal["catalog_only"]
    transport: Literal["mcp_candidate"]
    requires_approval: Literal[True]
    executable: Literal[False]


class AgentRuntimeSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=120)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AgentRuntimeSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID | None
    report_id: uuid.UUID
    title: str
    status: str
    active_job_id: uuid.UUID | None
    next_sequence: int
    revision: int
    last_message_at: datetime | None
    last_error_code: str | None
    next_event_sequence: int
    next_checkpoint_sequence: int
    context_summary_through_sequence: int
    compaction_count: int
    last_checkpoint_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentRuntimeMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=12000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content must not be blank")
        return cleaned


class AgentRuntimeMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    session_id: uuid.UUID
    sequence: int
    role: str
    content: str
    evidence_refs: list[dict[str, Any]]
    in_reply_to_message_id: uuid.UUID | None
    provider_name: str | None
    model_name: str | None
    token_usage: dict[str, int | None] | None
    created_at: datetime


class AgentRuntimeMessageListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AgentRuntimeMessageRead]
    total: int
    limit: int


class AgentRuntimeTurnAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    session_id: uuid.UUID
    job_id: uuid.UUID
    user_message_id: uuid.UUID
    revision: int



class AgentRuntimeToolCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    session_id: uuid.UUID
    user_message_id: uuid.UUID
    tool_key: str
    tool_version: str
    tool_description: str
    reason: str
    arguments: dict[str, Any]
    status: str
    output_preview: dict[str, Any] | None = None
    error_code: str | None
    created_at: datetime
    approved_at: datetime | None
    rejected_at: datetime | None
    completed_at: datetime | None


class AgentRuntimeToolCallListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AgentRuntimeToolCallRead]
    limit: int


class AgentRuntimeToolCallDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    tool_call_id: uuid.UUID
    session_id: uuid.UUID
    job_id: uuid.UUID | None = None


class AgentRuntimeCheckpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    session_id: uuid.UUID
    sequence: int
    checkpoint_type: str
    through_message_sequence: int
    context_summary: str | None
    state_snapshot: dict[str, Any]
    created_at: datetime


class AgentRuntimeCheckpointListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AgentRuntimeCheckpointRead]
    total: int
    limit: int
