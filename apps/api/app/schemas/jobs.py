"""Job API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: str
    status: str
    priority: int
    report_id: uuid.UUID | None
    attempt_count: int
    max_attempts: int
    available_at: datetime
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None


class JobEnqueueRequest(BaseModel):
    job_type: str = Field(..., min_length=1, max_length=200)
    payload: dict | None = None
    report_id: uuid.UUID | None = None
    priority: int = Field(default=0, ge=0)
    max_attempts: int | None = Field(default=None, ge=1, le=20)
    idempotency_key: str | None = Field(default=None, max_length=500)
    available_at: datetime | None = None


class JobCancelResponse(BaseModel):
    job: JobResponse
