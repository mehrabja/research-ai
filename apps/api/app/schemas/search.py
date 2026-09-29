from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SearchResult(BaseModel):
    id: uuid.UUID
    resource_type: Literal["project", "report", "source", "file"]
    title: str
    snippet: str | None = None
    updated_at: datetime
    project_id: uuid.UUID | None = None
    report_id: uuid.UUID | None = None


class SearchResponse(BaseModel):
    query: str
    workspace_id: uuid.UUID
    items: list[SearchResult]
    total: int
