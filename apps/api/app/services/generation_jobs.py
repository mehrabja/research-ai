"""Enqueue helpers for report-generation jobs."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domain.jobs import JobTypes
from app.services import jobs as jobs_service
from app.services.embedding_profile import (
    get_current_embedding_profile_id,
)
from app.services.generation_profile import (
    get_current_generation_profile_id,
)
from app.services.reports import get_report


def build_generation_job_idempotency_key(
    *,
    report_id: uuid.UUID,
    generation_profile_id: str,
    embedding_profile_id: str,
) -> str:
    return (
        f"generate_report:{report_id}:"
        f"{generation_profile_id}:"
        f"{embedding_profile_id}"
    )


def enqueue_report_generation_job(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    idempotency_key: str | None = None,
    priority: int = 0,
    max_attempts: int | None = None,
) -> jobs_service.EnqueueResult:
    get_report(db, user_id=user_id, report_id=report_id)

    gen_profile_id = get_current_generation_profile_id()
    emb_profile_id = get_current_embedding_profile_id()

    effective_key = (
        idempotency_key
        or build_generation_job_idempotency_key(
            report_id=report_id,
            generation_profile_id=gen_profile_id,
            embedding_profile_id=emb_profile_id,
        )
    )

    return jobs_service.enqueue_job(
        db,
        job_type=JobTypes.GENERATE_REPORT,
        payload={"report_id": str(report_id)},
        idempotency_key=effective_key,
        report_id=report_id,
        user_id=user_id,
        priority=priority,
        max_attempts=max_attempts,
    )


__all__ = [
    "build_generation_job_idempotency_key",
    "enqueue_report_generation_job",
]
