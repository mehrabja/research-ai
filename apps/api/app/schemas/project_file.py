"""M19 — ProjectFile schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

FileKindLiteral = Literal[
    "document", "pdf", "image", "archive", "text", "code",
    "structured_data", "spreadsheet", "presentation", "unknown",
]
FileStatusLiteral = Literal[
    "uploaded", "processing", "ready", "failed", "deleted",
]
ExtractionStatusLiteral = Literal[
    "not_started", "queued", "processing", "completed", "failed",
    "not_supported",
]


class ProjectFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    original_filename: str
    normalized_filename: str
    extension: str | None
    size_bytes: int
    sha256: str
    client_mime_type: str | None
    detected_mime_type: str | None
    file_kind: FileKindLiteral
    status: FileStatusLiteral
    extraction_status: ExtractionStatusLiteral
    extraction_error: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ProjectFileListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    original_filename: str
    file_kind: FileKindLiteral
    size_bytes: int
    status: FileStatusLiteral
    extraction_status: ExtractionStatusLiteral
    created_at: datetime


class ProjectFileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    folder_id: uuid.UUID | None = None


class ProjectFileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProjectFileListItem]
    total: int
    limit: int
    offset: int
