"""Extraction response schema."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class SourceExtractionResponse(BaseModel):
    source_id: uuid.UUID
    status: str
    content_hash: str | None
    chunk_count: int
    content_type: str | None
    content_length: int | None
    extracted_at: datetime | None
    pipeline_version: str
