"""Canonical evidence contract shared across research pipelines."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceKind = Literal[
    "project_file",
    "m28_evidence",
    "m29_technical_fact",
    "m29_experiment_result",
    "m29_metric",
    "retrieval_chunk",
    "claim_evidence",
]


class EvidenceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int | None = Field(default=None, ge=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, gt=0)


class EvidenceRecord(BaseModel):
    """Stable cross-pipeline representation of one evidence item.

    evidence_id is the database identity of the originating record.
    kind identifies which pipeline owns that record.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_key: str = Field(min_length=3, max_length=300)
    evidence_id: uuid.UUID
    kind: EvidenceKind

    claim_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    project_file_id: uuid.UUID | None = None

    title: str | None = None
    text: str | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    support_level: str | None = None

    locator: EvidenceLocator = Field(default_factory=EvidenceLocator)
    provenance: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime | None = None
