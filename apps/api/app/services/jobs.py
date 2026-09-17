"""Job service.

Owns enqueue / claim / heartbeat / complete / fail / cancel / recovery.
All state changes go through ``validate_job_transition``.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    InvalidJobStateError,
    JobLeaseLostError,
    JobNotFoundError,
    JobPayloadTooLargeError,
)
from app.db.models.jobs import Job
from app.domain.jobs import validate_job_transition
from app.services.job_retry import decide_retry
from app.services.reports import get_report

logger = logging.getLogger(__name__)

_UNIQUE_VIOLATION = "23505"
_LEASE_MAX_MESSAGE = 500


@dataclass(frozen=True)
class EnqueueResult:
    job: Job
    created: bool


def enqueue_job(
    db: Session,
    *,
    job_type: str,
    payload: dict,
    idempotency_key: str | None = None,
    report_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    priority: int = 0,
    max_attempts: int | None = None,
    available_at: datetime | None = None,
) -> EnqueueResult:
    settings = get_settings()

    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(encoded) > settings.job_payload_max_bytes:
        raise JobPayloadTooLargeError()

    if report_id is not None and user_id is not None:
        get_report(db, user_id=user_id, report_id=report_id)

    effective_max = max_attempts or settings.job_default_max_attempts

    if idempotency_key is not None:
        existing = db.execute(
            select(Job).where(Job.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return EnqueueResult(job=existing, created=False)

    job = Job(
        job_type=job_type,
        payload=payload,
        idempotency_key=idempotency_key,
        report_id=report_id,
        user_id=user_id,
        priority=priority,
        max_attempts=effective_max,
        status="queued",
        attempt_count=0,
        available_at=available_at or datetime.now(UTC),
    )
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except IntegrityError as exc:
        db.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if sqlstate == _UNIQUE_VIOLATION and idempotency_key is not None:
            winner = db.execute(
                select(Job).where(
                    Job.idempotency_key == idempotency_key
                )
            ).scalar_one()
            return EnqueueResult(job=winner, created=False)
        raise
    except Exception:
        db.rollback()
        raise
    return EnqueueResult(job=job, created=True)


def get_job(
    db: Session, *, job_id: uuid.UUID, user_id: uuid.UUID | None
) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise JobNotFoundError()
    if user_id is not None and job.user_id != user_id:
        raise JobNotFoundError()
    return job


def list_jobs(
    db: Session,
    *,
    user_id: uuid.UUID,
    status: str | None = None,
    report_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[Job]:
    stmt = select(Job).where(Job.user_id == user_id)
    if status:
        stmt = stmt.where(Job.status == status)
    if report_id:
        stmt = stmt.where(Job.report_id == report_id)
    stmt = stmt.order_by(Job.created_at.desc()).limit(
        max(1, min(limit, 200))
    )
    return list(db.execute(stmt).scalars().all())


def claim_job(db: Session, *, worker_id: str) -> Job | None:
    now = datetime.now(UTC)
    try:
        stmt = (
            select(Job)
            .where(
                Job.status.in_(("queued", "retrying")),
                Job.available_at <= now,
                Job.attempt_count < Job.max_attempts,
            )
            .order_by(
                Job.priority.desc(),
                Job.available_at.asc(),
                Job.created_at.asc(),
                Job.id.asc(),
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = db.execute(stmt).scalar_one_or_none()
        if job is None:
            db.rollback()
            return None

        validate_job_transition(job.status, "processing")

        job.status = "processing"
        job.attempt_count = job.attempt_count + 1
        job.worker_id = worker_id
        job.started_at = now
        job.heartbeat_at = now
        job.completed_at = None
        job.failed_at = None

        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


def heartbeat_job(
    db: Session, *, job_id: uuid.UUID, worker_id: str
) -> bool:
    now = datetime.now(UTC)
    result = cast(
        CursorResult,
        db.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == "processing",
                Job.worker_id == worker_id,
            )
            .values(heartbeat_at=now, updated_at=now)
        ),
    )
    if result.rowcount == 0:
        db.rollback()
        return False
    db.commit()
    return True


def complete_job(
    db: Session, *, job_id: uuid.UUID, worker_id: str
) -> None:
    now = datetime.now(UTC)
    result = cast(
        CursorResult,
        db.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == "processing",
                Job.worker_id == worker_id,
            )
            .values(
                status="completed",
                completed_at=now,
                heartbeat_at=None,
                updated_at=now,
            )
        ),
    )
    if result.rowcount == 0:
        db.rollback()
        raise JobLeaseLostError()
    db.commit()


def fail_job(
    db: Session,
    *,
    job_id: uuid.UUID,
    worker_id: str,
    error_code: str,
    error_message: str,
) -> None:
    now = datetime.now(UTC)

    job = db.execute(
        select(Job)
        .where(
            Job.id == job_id,
            Job.status == "processing",
            Job.worker_id == worker_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if job is None:
        db.rollback()
        raise JobLeaseLostError()

    decision = decide_retry(
        error_code=error_code,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
    )

    sanitized_message = (
        error_message[:_LEASE_MAX_MESSAGE] if error_message else None
    )

    if decision.retry and decision.delay_seconds is not None:
        validate_job_transition("processing", "retrying")
        new_status = "retrying"
        new_available_at = now + timedelta(
            seconds=decision.delay_seconds
        )
        new_failed_at = None
    else:
        validate_job_transition("processing", "failed")
        new_status = "failed"
        new_available_at = job.available_at
        new_failed_at = now

    job.status = new_status
    job.available_at = new_available_at
    job.failed_at = new_failed_at
    job.heartbeat_at = None
    job.worker_id = None
    job.last_error_code = (
        "max_attempts_exceeded"
        if decision.error_code == "max_attempts_exceeded"
        else error_code
    )
    job.last_error_message = sanitized_message
    job.updated_at = now
    db.commit()


def cancel_job(
    db: Session, *, job_id: uuid.UUID, user_id: uuid.UUID | None
) -> Job:
    now = datetime.now(UTC)

    stmt = select(Job).where(Job.id == job_id).with_for_update()
    if user_id is not None:
        stmt = stmt.where(Job.user_id == user_id)
    job = db.execute(stmt).scalar_one_or_none()

    if job is None:
        db.rollback()
        raise JobNotFoundError()

    if job.status not in ("queued", "retrying"):
        db.rollback()
        raise InvalidJobStateError(
            f"cannot cancel job in status {job.status!r}"
        )

    validate_job_transition(job.status, "cancelled")

    result = cast(
        CursorResult,
        db.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status.in_(("queued", "retrying")),
            )
            .values(status="cancelled", updated_at=now)
        ),
    )
    if result.rowcount == 0:
        db.rollback()
        raise InvalidJobStateError("job is no longer cancellable")
    db.commit()
    db.refresh(job)
    return job


def reclaim_stale_jobs(db: Session, *, limit: int = 100) -> int:
    settings = get_settings()
    now = datetime.now(UTC)
    cutoff = now - timedelta(
        seconds=settings.job_processing_timeout_seconds
    )

    try:
        stmt = (
            select(Job)
            .where(
                Job.status == "processing",
                Job.heartbeat_at.is_not(None),
                Job.heartbeat_at < cutoff,
            )
            .order_by(Job.heartbeat_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = list(db.execute(stmt).scalars().all())
        if not jobs:
            db.rollback()
            return 0

        for job in jobs:
            job.worker_id = None
            job.heartbeat_at = None
            job.updated_at = now
            if job.attempt_count < job.max_attempts:
                validate_job_transition(job.status, "retrying")
                job.status = "retrying"
                job.available_at = now
                job.last_error_code = "lease_expired"
                job.last_error_message = (
                    "worker heartbeat expired before completion"
                )
            else:
                validate_job_transition(job.status, "failed")
                job.status = "failed"
                job.failed_at = now
                job.last_error_code = "lease_expired"
                job.last_error_message = (
                    "worker heartbeat expired and no attempts remain"
                )
        db.commit()
        return len(jobs)
    except Exception:
        db.rollback()
        raise


__all__ = [
    "EnqueueResult",
    "cancel_job",
    "claim_job",
    "complete_job",
    "enqueue_job",
    "fail_job",
    "get_job",
    "heartbeat_job",
    "list_jobs",
    "reclaim_stale_jobs",
]
