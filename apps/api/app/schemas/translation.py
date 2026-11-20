from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TranslationEnqueueRequest(BaseModel):
    source_version_id: uuid.UUID
    target_language: str


class TranslationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    source_version_id: uuid.UUID | None
    source_lang: str
    target_lang: str
    profile_id: str | None
    provider: str
    status: str
    created_at: datetime
    completed_at: datetime | None


class TranslationVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    translation_run_id: uuid.UUID
    content: str
    preservation_check_status: str
    preservation_details: dict[str, Any] | None


class TranslationCurrentResponse(BaseModel):
    run: TranslationRunRead
    version: TranslationVersionRead
