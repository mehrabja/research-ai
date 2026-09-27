"""Global search API schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class GlobalSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    id: uuid.UUID
    title: str
    snippet: str | None = None
    workspace_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    report_id: uuid.UUID | None = None
    url: str | None = None


class GlobalSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    items: list[GlobalSearchItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
