"""Manuscript draft/autosave API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ManuscriptDraftSaveRequest(BaseModel):
    revision: int = Field(..., ge=0)
    content: dict[str, Any]
    base_version_id: uuid.UUID | None = None


class ManuscriptDraftRead(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID
    base_version_id: uuid.UUID | None
    revision: int
    content: dict[str, Any]
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ManuscriptDraftSaveResponse(BaseModel):
    draft: ManuscriptDraftRead
    saved: bool
    conflict: bool = False


class ManuscriptSaveVersionRequest(BaseModel):
    expected_revision: int = Field(..., ge=0)


class ManuscriptRestoreVersionRequest(BaseModel):
    expected_revision: int = Field(..., ge=0)
