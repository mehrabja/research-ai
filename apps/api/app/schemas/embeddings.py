"""Embedding endpoint schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel


class SourceEmbeddingResponse(BaseModel):
    source_id: uuid.UUID
    total_chunks: int
    already_current: int
    embedded: int
    failed: int
    pending: int
    profile_id: str
    usage_input_tokens: int
