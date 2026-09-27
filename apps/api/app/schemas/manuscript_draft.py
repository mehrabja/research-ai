from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ManuscriptDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID
    base_version_id: uuid.UUID
    revision: int
    content: dict[str, Any]
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ManuscriptDraftWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_version_id: uuid.UUID
    revision: int = Field(..., ge=0)
    content: dict[str, Any]


class ManuscriptDraftCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_version_id: uuid.UUID
    revision: int = Field(..., ge=0)


class ManuscriptDraftConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = "MANUSCRIPT_DRAFT_CONFLICT"
    message: str
    current_base_version_id: uuid.UUID
    current_revision: int
