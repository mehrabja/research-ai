from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CanvasNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    type: Literal["idea", "evidence", "draft", "note"]
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=5_000)
    x: float = Field(default=0, ge=-100_000, le=100_000)
    y: float = Field(default=0, ge=-100_000, le=100_000)
    ref_type: Literal[
        "source",
        "evidence",
        "project_file",
        "manuscript_section",
    ] | None = None
    ref_id: uuid.UUID | None = None
    evidence_key: str | None = Field(default=None, max_length=300)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanvasEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)


class CanvasViewport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(default=0, ge=-100_000, le=100_000)
    y: float = Field(default=0, ge=-100_000, le=100_000)
    zoom: float = Field(default=1.0, ge=0.25, le=4.0)


class ResearchCanvasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    revision: int
    nodes: list[CanvasNode]
    edges: list[CanvasEdge]
    viewport: CanvasViewport
    updated_by_user: uuid.UUID | None
    updated_at: datetime


class ResearchCanvasUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[CanvasNode] = Field(max_length=100)
    edges: list[CanvasEdge] = Field(max_length=200)
    viewport: CanvasViewport = Field(default_factory=CanvasViewport)
    expected_revision: int | None = Field(default=None, ge=1)
