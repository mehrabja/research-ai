"""Report request/response schemas.

Validation constraints are minimal on purpose: the underlying columns
are TEXT (unbounded) and this milestone has no evidence-based
column-size requirement.

Server-controlled fields such as ``id``, ``user_id``, ``status``,
timestamps, and ``deleted_at`` are never accepted from clients.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportCreate(BaseModel):
    topic: str = Field(..., min_length=1)
    output_language: str = Field(..., min_length=1)
    domain: str | None = None
    tone: str | None = None
    length: str | None = None
    structure_template: str | None = None
    audience_level: str | None = None
    project_id: uuid.UUID | None = None


class ReportUpdate(BaseModel):
    """Partial update with explicit-null semantics."""

    topic: str | None = Field(default=None, min_length=1)
    output_language: str | None = Field(default=None, min_length=1)
    domain: str | None = None
    tone: str | None = None
    length: str | None = None
    structure_template: str | None = None
    audience_level: str | None = None

    @model_validator(mode="after")
    def _reject_null_required(self) -> ReportUpdate:
        for field in ("topic", "output_language"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be set to null")
        return self


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic: str
    domain: str | None
    status: str
    tone: str | None
    length: str | None
    structure_template: str | None
    output_language: str
    audience_level: str | None
    project_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
