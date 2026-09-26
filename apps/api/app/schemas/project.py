"""M18-A — Project schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProjectStatusLiteral = Literal["draft", "active", "archived"]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    domain: str | None = Field(default=None, max_length=10_000)
    research_objective: str | None = Field(default=None, max_length=10_000)
    research_questions: list[str] = Field(default_factory=list, max_length=100)
    hypotheses: list[str] = Field(default_factory=list, max_length=100)
    scope: str | None = Field(default=None, max_length=10_000)
    constraints: str | None = Field(default=None, max_length=10_000)
    status: ProjectStatusLiteral = "draft"


class ProjectUpdate(BaseModel):
    """Partial update.

    Routes MUST call ``model_dump(exclude_unset=True)`` so that
    ``{}`` (no-op) and ``{"description": null}`` (clear) are
    distinguishable.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    domain: str | None = Field(default=None, max_length=10_000)
    research_objective: str | None = Field(default=None, max_length=10_000)
    research_questions: list[str] | None = Field(default=None, max_length=100)
    hypotheses: list[str] | None = Field(default=None, max_length=100)
    scope: str | None = Field(default=None, max_length=10_000)
    constraints: str | None = Field(default=None, max_length=10_000)
    status: ProjectStatusLiteral | None = None

    @model_validator(mode="after")
    def _reject_null_for_nonnullable(self) -> ProjectUpdate:
        for field in ("name", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be set to null")
        return self


class ProjectRead(BaseModel):
    workspace_id: uuid.UUID
    id: uuid.UUID
    name: str
    description: str | None
    domain: str | None
    research_objective: str | None
    research_questions: list[str]
    hypotheses: list[str]
    scope: str | None
    constraints: str | None
    status: ProjectStatusLiteral
    report_count: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class ProjectListItem(BaseModel):
    workspace_id: uuid.UUID
    id: uuid.UUID
    name: str
    domain: str | None
    status: ProjectStatusLiteral
    report_count: int
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    items: list[ProjectListItem]
    total: int
    limit: int
    offset: int


class ProjectReportListItem(BaseModel):
    id: uuid.UUID
    topic: str
    status: str
    output_language: str
    updated_at: datetime


class ProjectReportListResponse(BaseModel):
    items: list[ProjectReportListItem]
    total: int
    limit: int
    offset: int
