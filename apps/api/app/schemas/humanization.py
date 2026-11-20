from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class HumanizationEnqueueRequest(BaseModel):
    version_id: uuid.UUID
    detection_run_id: uuid.UUID
    policy_version: str | None = None


class HumanizationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    stage: str
    language: str
    status: str
    detection_score_before: float | None
    detection_score_after: float | None
    cost_usd: float | None
    tokens_used: int | None
    source_version_id: uuid.UUID | None
    detection_run_id: uuid.UUID | None
    output_version_id: uuid.UUID | None
    policy_version: str | None
    diff_summary: dict[str, Any] | None
    skipped_oversize: list[str]
    skipped_preservation: list[dict[str, str]]
    completed_at: datetime | None
    created_at: datetime


class HumanizationCurrentResponse(BaseModel):
    run: HumanizationRunRead
    output_version: dict[str, Any] | None = None
