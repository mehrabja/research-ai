"""Detection routes."""
from __future__ import annotations

import uuid
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.pipeline import DetectionRun
from app.db.models.user import User
from app.db.session import get_db
from app.domain.detection import DetectionLabel
from app.schemas.detection import (
    DetectionEnqueueResponse,
    DetectionResultResponse,
)
from app.services import detection_jobs
from app.services.reports import get_report

router = APIRouter(prefix="/reports", tags=["detection"])

_StatusLiteral = Literal["completed", "failed"]


@router.post(
    "/{report_id}/versions/{version_id}/detect",
    response_model=DetectionEnqueueResponse,
    status_code=201,
)
def enqueue_detection(
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DetectionEnqueueResponse:
    result = detection_jobs.enqueue_detection_job(
        db,
        user_id=current_user.id,
        report_id=report_id,
        version_id=version_id,
    )
    return DetectionEnqueueResponse(
        job_id=result.job.id,
        report_id=report_id,
        version_id=version_id,
        status="queued",
    )


@router.get(
    "/{report_id}/versions/{version_id}/detection",
    response_model=DetectionResultResponse,
)
def get_detection(
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DetectionResultResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)

    row = db.execute(
        select(DetectionRun)
        .where(
            DetectionRun.report_id == report_id,
            DetectionRun.version_id == version_id,
            DetectionRun.status == "completed",
        )
        .order_by(DetectionRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="not found")

    meta = row.detection_meta or {}
    label_value = meta.get("label", "unknown")
    return DetectionResultResponse(
        run_id=row.id,
        report_id=row.report_id,
        version_id=row.version_id or version_id,
        profile_id=meta.get("profile_id", ""),
        provider=row.provider,
        model=meta.get("model", ""),
        probability=(
            float(row.overall_score)
            if row.overall_score is not None
            else None
        ),
        label=cast(DetectionLabel, label_value),
        input_hash=meta.get("input_hash", ""),
        status=cast(_StatusLiteral, row.status),
    )
