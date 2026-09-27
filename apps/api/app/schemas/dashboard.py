"""Dashboard aggregate API schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DashboardStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_projects: int
    saved_sources: int
    evidence_items: int
    active_jobs: int
    storage_bytes: int
    ai_generation_units: int
    ai_generation_limit: int | None
    workspace_count: int
