"""Enqueue helpers for embedding jobs.

This module owns the M11 enqueue path for ``embedding_source``. It
does NOT perform embedding; it validates ownership and delegates
job creation to the M10 ``enqueue_job`` service.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domain.jobs import JobTypes
from app.services import jobs as jobs_service
from app.services.embedding_profile import (
    get_current_embedding_profile_id,
)
from app.services.sources import get_source_for_report


def build_embedding_job_idempotency_key(
    *,
    report_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: str,
) -> str:
    """Deterministic key so a duplicate enqueue of the same logical
    work returns the existing job.

    Profile is part of the key so a profile bump produces a fresh
    job (as required for re-embedding after model changes).
    """
    return (
        f"embedding_source:{report_id}:{source_id}:{profile_id}"
    )


def enqueue_source_embedding_job(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    source_id: uuid.UUID,
    idempotency_key: str | None = None,
    priority: int = 0,
    max_attempts: int | None = None,
) -> jobs_service.EnqueueResult:
    """Validate ownership and enqueue an ``embedding_source`` job."""
    get_source_for_report(
        db,
        user_id=user_id,
        report_id=report_id,
        source_id=source_id,
    )

    profile_id = get_current_embedding_profile_id()

    effective_key = (
        idempotency_key
        or build_embedding_job_idempotency_key(
            report_id=report_id,
            source_id=source_id,
            profile_id=profile_id,
        )
    )

    return jobs_service.enqueue_job(
        db,
        job_type=JobTypes.EMBEDDING_SOURCE,
        payload={
            "report_id": str(report_id),
            "source_id": str(source_id),
        },
        idempotency_key=effective_key,
        report_id=report_id,
        user_id=user_id,
        priority=priority,
        max_attempts=max_attempts,
    )


__all__ = [
    "build_embedding_job_idempotency_key",
    "enqueue_source_embedding_job",
]
