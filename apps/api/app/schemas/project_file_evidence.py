from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProjectFileEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    file_kind: str
    extraction_status: str
    evidence_status: Literal[
        "processing",
        "synced",
        "awaiting_report",
        "unavailable",
    ]
    source_count: int
    chunk_count: int
    source_ids: list[uuid.UUID]
    report_ids: list[uuid.UUID]
    last_synced_at: datetime | None


class ProjectFileEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProjectFileEvidenceRead]
    total: int


class ProjectFileEvidenceSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: uuid.UUID | None = None


class ProjectFileEvidenceSyncResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    synced_reports: int
    synced_files: int
