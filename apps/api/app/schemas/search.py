"""M39 global search schemas."""
from __future__ import annotations
import uuid
from typing import Literal
from pydantic import BaseModel, ConfigDict

class SearchResultRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["project", "report", "source", "file"]
    id: uuid.UUID
    title: str
    subtitle: str | None = None
    project_id: uuid.UUID | None = None

class GlobalSearchResponse(BaseModel):
    query: str
    items: list[SearchResultRead]
    total: int
