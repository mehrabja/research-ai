from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PdfWorkspaceDocumentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    original_filename: str
    size_bytes: int
    status: str
    extraction_status: str
    content_url: str


class PdfAnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    file_id: uuid.UUID
    created_by_user: uuid.UUID
    kind: Literal["highlight", "note"]
    page_number: int
    selected_text: str | None
    note: str | None
    rect: dict | None
    annotation_meta: dict | None
    created_at: datetime
    updated_at: datetime


class PdfWorkspaceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    active_file_id: uuid.UUID | None
    page_number: int
    zoom: float
    scroll_x: float
    scroll_y: float
    documents: list[PdfWorkspaceDocumentRead]
    annotations: list[PdfAnnotationRead]
    updated_at: datetime


class PdfWorkspaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_file_id: uuid.UUID | None = None
    page_number: int = Field(default=1, ge=1)
    zoom: float = Field(default=1.0, ge=0.25, le=4.0)
    scroll_x: float = Field(default=0.0, ge=0)
    scroll_y: float = Field(default=0.0, ge=0)


class PdfAnnotationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: uuid.UUID
    kind: Literal["highlight", "note"]
    page_number: int = Field(default=1, ge=1)
    selected_text: str | None = Field(default=None, max_length=10_000)
    note: str | None = Field(default=None, max_length=10_000)
    rect: dict | None = None


class PdfAnnotationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["highlight", "note"] | None = None
    page_number: int | None = Field(default=None, ge=1)
    selected_text: str | None = Field(default=None, max_length=10_000)
    note: str | None = Field(default=None, max_length=10_000)
    rect: dict | None = None
