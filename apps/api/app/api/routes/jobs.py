"""Job API routes.

Capability checks come from ``app.domain.jobs`` so the API layer
never imports worker code.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.rate_limit_deps import enforce_user_rate_limit
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
    JobTypes,
)
from app.schemas.jobs import (
    JobCancelResponse,
    JobEnqueueRequest,
    JobResponse,
)
from app.services import embedding_jobs, generation_jobs
from app.services import jobs as jobs_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _parse_embedding_payload(
    payload: dict,
) -> tuple[uuid.UUID, uuid.UUID]:
    report_raw = payload.get("report_id")
    source_raw = payload.get("source_id")
    if not isinstance(report_raw, str) or not isinstance(
        source_raw, str
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PAYLOAD",
                "message": (
                    "embedding_source requires report_id and source_id"
                ),
            },
        )
    try:
        return uuid.UUID(report_raw), uuid.UUID(source_raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PAYLOAD",
                "message": (
                    "report_id and source_id must be valid UUIDs"
                ),
            },
        ) from exc


def _parse_generation_payload(payload: dict) -> uuid.UUID:
    raw = payload.get("report_id")
    if not isinstance(raw, str):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PAYLOAD",
                "message": "generate_report requires report_id",
            },
        )
    try:
        return uuid.UUID(raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PAYLOAD",
                "message": "report_id must be a valid UUID",
            },
        ) from exc


@router.post(
    "",
    response_model=JobResponse,
    status_code=201,
    dependencies=[
        Depends(
            enforce_user_rate_limit(
                "jobs_enqueue",
                setting_name="rate_limit_enqueue_per_minute",
            )
        )
    ],
)
def enqueue_job(
    payload: JobEnqueueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    # بدنه بدون تغییر
    if payload.job_type in RESERVED_JOB_TYPES:
        raise UnknownJobTypeError(
            f"job_type {payload.job_type!r} is reserved but not "
            "executable"
        )
    if payload.job_type not in EXECUTABLE_JOB_TYPES:
        raise UnknownJobTypeError(
            f"unknown job_type: {payload.job_type!r}"
        )

    if payload.job_type == JobTypes.EMBEDDING_SOURCE:
        report_id, source_id = _parse_embedding_payload(
            payload.payload or {}
        )
        result = embedding_jobs.enqueue_source_embedding_job(
            db,
            user_id=current_user.id,
            report_id=report_id,
            source_id=source_id,
            idempotency_key=payload.idempotency_key,
            priority=payload.priority,
            max_attempts=payload.max_attempts,
        )
        return result.job

    if payload.job_type == JobTypes.GENERATE_REPORT:
        report_id = _parse_generation_payload(payload.payload or {})
        result = generation_jobs.enqueue_report_generation_job(
            db,
            user_id=current_user.id,
            report_id=report_id,
            idempotency_key=payload.idempotency_key,
            priority=payload.priority,
            max_attempts=payload.max_attempts,
        )
        return result.job

    if payload.job_type == JobTypes.DETECT_REPORT:
        body = payload.payload or {}
        report_raw = body.get("report_id")
        version_raw = body.get("version_id")
        if not isinstance(report_raw, str) or not isinstance(
            version_raw, str
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_PAYLOAD",
                    "message": (
                        "detect_report requires report_id and version_id"
                    ),
                },
            )
        try:
            report_id = uuid.UUID(report_raw)
            version_id = uuid.UUID(version_raw)
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_PAYLOAD",
                    "message": "ids must be valid UUIDs",
                },
            ) from exc

        from app.services import detection_jobs

        result = detection_jobs.enqueue_detection_job(
            db,
            user_id=current_user.id,
            report_id=report_id,
            version_id=version_id,
            idempotency_key=payload.idempotency_key,
            priority=payload.priority,
            max_attempts=payload.max_attempts,
        )
        return result.job

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


@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    return jobs_service.retry_failed_job(
        db,
        job_id=job_id,
        user_id=current_user.id,
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
