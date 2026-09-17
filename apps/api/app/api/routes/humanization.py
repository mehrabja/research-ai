"""Humanization routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.humanization import HumanizationEnqueueRequest
from app.services import humanization_jobs as humanization_jobs_service
from app.services import jobs as jobs_service

router = APIRouter(prefix="/reports", tags=["humanization"])


@router.post(
    "/{report_id}/humanization/enqueue",
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_humanization(
    report_id: uuid.UUID,
    body: HumanizationEnqueueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        job_id = humanization_jobs_service.enqueue_humanization_job(
            db=db,
            user_id=current_user.id,
            report_id=report_id,
            version_id=body.version_id,
            detection_run_id=body.detection_run_id,
            jobs_service=jobs_service,
            policy_version=body.policy_version,
        )
        db.commit()
    except humanization_jobs_service.HumanizationEnqueueOwnershipError:
        db.rollback()
        raise HTTPException(status_code=404, detail="not found") from None
    except humanization_jobs_service.HumanizationEnqueueStateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"job_id": str(job_id), "status": "queued"}
