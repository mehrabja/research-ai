"""M39 dashboard and export schemas."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict

class DashboardSummary(BaseModel):
    model_config=ConfigDict(extra="forbid")
    workspace_id: uuid.UUID
    projects: int
    reports: int
    files: int
    storage_bytes: int
    active_jobs: int
    current_plan: str
    usage: dict[str,int]

class AuditEventRead(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    source: str
    event_type: str
    user_id: uuid.UUID | None
    project_id: uuid.UUID | None
    report_id: uuid.UUID | None
    created_at: datetime
    metadata: dict[str,Any] | None

class AuditEventListResponse(BaseModel):
    items: list[AuditEventRead]
    total: int

class ProjectExportManifest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    project: dict[str,Any]
    files: list[dict[str,Any]]
    reports: list[dict[str,Any]]
    sources: list[dict[str,Any]]
    generated_at: datetime
