"""M25 — Knowledge graph schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeGraphNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    graph_version_id: uuid.UUID
    project_id: uuid.UUID
    node_type: str
    node_key: str
    entity_id: uuid.UUID
    label: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeGraphEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    graph_version_id: uuid.UUID
    project_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relation_type: str
    provenance_type: str
    provenance_ref: str | None
    confidence: float | None
    weight: float
    edge_key: str
    created_at: datetime
    updated_at: datetime


class KnowledgeGraphRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    status: str
    graph_version: str
    context_hash: str
    source_literature_run_id: uuid.UUID | None
    research_plan_id: uuid.UUID | None
    node_count: int
    edge_count: int
    graph_meta: dict[str, Any] | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class KnowledgeGraphSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graph_version_id: uuid.UUID
    version: int
    status: str
    node_count: int
    edge_count: int
    node_type_counts: dict[str, int] = Field(default_factory=dict)
    relation_type_counts: dict[str, int] = Field(default_factory=dict)
    context_hash: str
    graph_version: str


class KnowledgeGraphBuildResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    job_id: uuid.UUID | None = None
    graph: KnowledgeGraphRead | None = None


class KnowledgeGraphGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    force: bool = False
    async_: bool | None = Field(default=None, alias="async")


class KnowledgeGraphNeighborRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edge_id: uuid.UUID
    relation_type: str
    provenance_type: str
    provenance_ref: str | None
    confidence: float | None
    weight: float
    direction: str
    neighbor: dict[str, Any]


class KnowledgeGraphQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_node_id: uuid.UUID
    max_depth: int | None = Field(default=None, ge=1, le=10)
    max_nodes: int | None = Field(default=None, ge=1, le=10_000)
    relation_types: list[str] | None = None


class KnowledgeGraphQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graph_version_id: uuid.UUID
    start_node_id: uuid.UUID
    max_depth: int
    max_nodes: int
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeGraphNodeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[KnowledgeGraphNodeRead]
    total: int
    limit: int
    offset: int
