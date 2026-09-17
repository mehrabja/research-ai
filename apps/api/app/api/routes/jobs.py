"""Job API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import (
    InvalidJobStateError,
    UnknownJobTypeError,
)
from app.db.models.jobs import Job
from app.db.models.user import User
from app.db.session import get_db
from app.domain.jobs import (
    ALL_JOB_STATUSES,
    EXECUTABLE_JOB_TYPES,
    RESERVED_JOB_TYPES,
)
from app.schemas.jobs import (
    JobCancelResponse,
    JobEnqueueRequest,
    JobResponse,
)
from app.services import jobs as jobs_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
def enqueue_job(
    payload: JobEnqueueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    if payload.job_type in RESERVED_JOB_TYPES:
        raise UnknownJobTypeError(
            f"job_type {payload.job_type!r} is reserved but not "
            "executable in M10"
        )
    if payload.job_type not in EXECUTABLE_JOB_TYPES:
        raise UnknownJobTypeError(
            f"unknown job_type: {payload.job_type!r}"
        )

    result = jobs_service.enqueue_job(
        db,
        job_type=payload.job_type,
        payload=payload.payload or {},
        idempotency_key=payload.idempotency_key,
        report_id=payload.report_id,
        user_id=current_user.id,
        priority=payload.priority,
        max_attempts=payload.max_attempts,
        available_at=payload.available_at,
    )
    return result.job


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    return jobs_service.get_job(
        db, job_id=job_id, user_id=current_user.id
    )


@router.get("", response_model=list[JobResponse])
def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    report_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Job]:
    if status is not None and status not in ALL_JOB_STATUSES:
        raise InvalidJobStateError(f"unknown status: {status!r}")
    return jobs_service.list_jobs(
        db,
        user_id=current_user.id,
        status=status,
        report_id=report_id,
        limit=limit,
    )


@router.post("/{job_id}/cancel", response_model=JobCancelResponse)
def cancel_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobCancelResponse:
    job = jobs_service.cancel_job(
        db, job_id=job_id, user_id=current_user.id
    )
    return JobCancelResponse(job=JobResponse.model_validate(job))
