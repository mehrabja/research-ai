"""Report version request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportVersionCreate(BaseModel):
    language: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)


class ReportVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    version_number: int
    language: str
    content: str
    created_by_user: bool
    change_type: str | None
    created_at: datetime
