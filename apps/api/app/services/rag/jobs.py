"""M26 — Enqueue helper for advanced RAG jobs.

Idempotency is enforced at two layers:
    1. Job idempotency_key = f"advanced_rag_retrieve:{project_id}:{context_hash}".
       ``enqueue_job`` returns the existing job for a matching key.
    2. RetrievalRun cache identity = same context_hash. Even if a
       second job is created, ``retrieve_research_context`` reuses
       the completed run instead of recomputing.
"""
from __future__ import annotations

import contextlib
import logging
import uuid
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import jobs as jobs_service

logger = logging.getLogger(__name__)


class AdvancedRAGJobPayload(BaseModel):
    """Durable payload for ``advanced_rag_retrieve`` jobs."""

    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    user_id: uuid.UUID
    query: str = Field(min_length=1, max_length=4000)
    context_hash: str = Field(min_length=1, max_length=128)

    report_id: uuid.UUID | None = None
    plan_section_id: uuid.UUID | None = None
    evidence_requirement_id: uuid.UUID | None = None

    mode: Literal["semantic", "lexical", "hybrid"]
    algorithm: Literal["exact", "ann"]

    max_results: int | None = Field(default=None, ge=1)

    graph_expansion_enabled: bool | None = None
    memory_enabled: bool | None = None
    diversity_enabled: bool | None = None

    min_year: int | None = Field(default=None, ge=1000, le=2200)
    max_year: int | None = Field(default=None, ge=1000, le=2200)
    required_full_text: bool = False

    allowed_source_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def _validate_year_range(self) -> AdvancedRAGJobPayload:
        if (
            self.min_year is not None
            and self.max_year is not None
            and self.min_year > self.max_year
        ):
            raise ValueError("min_year cannot exceed max_year")
        return self


def enqueue_advanced_rag_retrieve(
    db: Session,
    *,
    payload: AdvancedRAGJobPayload,
) -> uuid.UUID | None:
    try:
        payload_dict = payload.model_dump(mode="json")
        enqueued = jobs_service.enqueue_job(
            db,
            job_type="advanced_rag_retrieve",
            payload=payload_dict,
            idempotency_key=(
                f"advanced_rag_retrieve:{payload.project_id}:"
                f"{payload.context_hash}"
            ),
            user_id=payload.user_id,
            max_attempts=get_settings().rag_job_max_attempts,
        )
        return enqueued.job.id
    except Exception:
        logger.exception(
            "rag_enqueue_failed project_id=%s", payload.project_id
        )
        with contextlib.suppress(Exception):
            db.rollback()
        return None


__all__ = [
    "AdvancedRAGJobPayload",
    "enqueue_advanced_rag_retrieve",
]
