"""Humanization routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.humanization import HumanizationRun
from app.db.models.report import ReportVersion
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.humanization import (
    HumanizationCurrentResponse,
    HumanizationEnqueueRequest,
    HumanizationRunRead,
)
from app.services import humanization_jobs as humanization_jobs_service
from app.services import jobs as jobs_service
from app.services.reports import get_report

router = APIRouter(prefix="/reports", tags=["humanization"])


def _run_read(run: HumanizationRun) -> HumanizationRunRead:
    policy = run.policy_json or {}
    diff_summary = policy.get("diff_summary")
    return HumanizationRunRead(
        id=run.id,
        report_id=run.report_id,
        stage=run.stage,
        language=run.language,
        status=run.status,
        detection_score_before=(
            float(run.detection_score_before)
            if run.detection_score_before is not None
            else None
        ),
        detection_score_after=(
            float(run.detection_score_after)
            if run.detection_score_after is not None
            else None
        ),
        cost_usd=float(run.cost_usd) if run.cost_usd is not None else None,
        tokens_used=run.tokens_used,
        source_version_id=(
            uuid.UUID(str(policy["source_version_id"]))
            if policy.get("source_version_id")
            else None
        ),
        detection_run_id=(
            uuid.UUID(str(policy["detection_run_id"]))
            if policy.get("detection_run_id")
            else None
        ),
        output_version_id=(
            uuid.UUID(str(policy["output_version_id"]))
            if policy.get("output_version_id")
            else None
        ),
        policy_version=policy.get("policy_version"),
        diff_summary=diff_summary if isinstance(diff_summary, dict) else None,
        skipped_oversize=[
            str(item) for item in policy.get("skipped_oversize", [])
            if isinstance(item, (str, int))
        ],
        skipped_preservation=[
            item for item in policy.get("skipped_preservation", [])
            if isinstance(item, dict)
        ],
        completed_at=run.completed_at,
        created_at=run.created_at,
    )


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


@router.get(
    "/{report_id}/humanization/current",
    response_model=HumanizationCurrentResponse,
)
def get_current_humanization(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HumanizationCurrentResponse:
    get_report(db, user_id=current_user.id, report_id=report_id)
    run = db.execute(
        select(HumanizationRun)
        .where(
            HumanizationRun.report_id == report_id,
            HumanizationRun.stage == "pre_translation",
        )
        .order_by(
            HumanizationRun.created_at.desc(),
            HumanizationRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="not found")

    output = None
    output_id = (run.policy_json or {}).get("output_version_id")
    if output_id:
        try:
            output_uuid = uuid.UUID(str(output_id))
        except ValueError:
            output_uuid = None
        if output_uuid is not None:
            version = db.execute(
                select(ReportVersion).where(
                    ReportVersion.id == output_uuid,
                    ReportVersion.report_id == report_id,
                )
            ).scalar_one_or_none()
            if version is not None:
                output = {
                    "id": version.id,
                    "report_id": version.report_id,
                    "version_number": version.version_number,
                    "language": version.language,
                    "content": version.content,
                    "change_type": version.change_type,
                    "source_version_id": version.source_version_id,
                    "created_at": version.created_at,
                }

    return HumanizationCurrentResponse(
        run=_run_read(run),
        output_version=output,
    )
