"""M15 — Pre-translation review schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewEventResponse(BaseModel):
    id: uuid.UUID
    action: str
    user_id: uuid.UUID
    version_id: uuid.UUID | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PreTranslationReviewResponse(BaseModel):
    report_id: uuid.UUID
    status: str
    version_id: uuid.UUID
    version_number: int
    language: str
    content: str
    change_type: str | None
    source_version_id: uuid.UUID | None
    review_stage: str
    review_events: list[ReviewEventResponse]


class PreTranslationEditRequest(BaseModel):
    version_id: uuid.UUID
    content: str = Field(..., min_length=1, max_length=500_000)
    notes: str | None = Field(None, max_length=2_000)


class PreTranslationApproveRequest(BaseModel):
    version_id: uuid.UUID


class PreTranslationRequestChangesRequest(BaseModel):
    version_id: uuid.UUID
    notes: str = Field(..., min_length=1, max_length=2_000)


class PreTranslationRejectRequest(BaseModel):
    version_id: uuid.UUID
    notes: str = Field(..., min_length=1, max_length=2_000)


class PostTranslationReviewResponse(BaseModel):
    report_id: uuid.UUID
    status: str
    version_id: uuid.UUID
    version_number: int
    language: str
    content: str
    change_type: str | None
    source_version_id: uuid.UUID | None
    review_stage: str
    review_events: list[ReviewEventResponse]
