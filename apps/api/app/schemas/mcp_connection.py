"""API contracts for workspace-scoped MCP server registrations."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MCPServerProfileRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_key: str
    display_name: str
    description: str
    authentication_required: bool
    transport: Literal["streamable_http"] = "streamable_http"


class MCPConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")


class MCPConnectionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    workspace_id: uuid.UUID
    profile_key: str
    profile_name: str
    status: Literal["enabled", "disabled"]
    discovery_status: Literal["never", "success", "failed"]
    protocol_version: str | None
    server_name: str | None
    server_version: str | None
    tool_count: int
    resource_count: int
    resource_template_count: int
    prompt_count: int
    capability_snapshot: dict[str, Any]
    last_discovered_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime


class MCPDiscoverySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection: MCPConnectionRead
    tools_discovered: int
    resources_discovered: int
    prompts_discovered: int
    executable_tools_added: int = 0
