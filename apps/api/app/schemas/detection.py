"""Detection API schemas."""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DetectionEnqueueResponse(BaseModel):
    job_id: uuid.UUID
    report_id: uuid.UUID
    version_id: uuid.UUID
    status: Literal["queued"]


class DetectionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    report_id: uuid.UUID
    version_id: uuid.UUID
    profile_id: str
    provider: str
    model: str
    probability: float | None
    label: Literal["low", "medium", "high", "unknown"]
    input_hash: str
    status: Literal["completed", "failed"]
