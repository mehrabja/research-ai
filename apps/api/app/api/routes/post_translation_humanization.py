"""M17 — Post-translation humanization recovery routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.humanization import HumanizationRun
from app.db.models.report import Report
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.post_translation_humanization import (
    PostTranslationHumanizationCurrentResponse,
)
from app.services import post_translation_humanization_jobs as m17_jobs
from app.services.humanization_profile import (
    build_post_translation_policy_from_settings,
)

router = APIRouter(prefix="/reports", tags=["post_translation_humanization"])


class PostTranslationHumanizationEnqueueRequest(BaseModel):
    translation_run_id: uuid.UUID
    translation_version_id: uuid.UUID


@router.post(
    "/{report_id}/post-translation-humanization/enqueue",
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_post_translation_humanization(
    report_id: uuid.UUID,
    body: PostTranslationHumanizationEnqueueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    try:
        result = m17_jobs.enqueue_post_translation_humanization_job(
            db=db,
            user_id=current_user.id,
            report_id=report_id,
            translation_run_id=body.translation_run_id,
            translation_version_id=body.translation_version_id,
            policy_version=build_post_translation_policy_from_settings().version,
        )
        db.commit()
    except m17_jobs.PostTranslationHumanizationEnqueueOwnershipError:
        db.rollback()
        raise HTTPException(status_code=404, detail="not found") from None
    except m17_jobs.PostTranslationHumanizationEnqueueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503, detail=f"enqueue failed: {exc}"
        ) from None

    return {
        "job_id": str(result.job_id) if result.job_id else None,
        "status": result.outcome.value,
    }

@router.get(
    "/{report_id}/post-translation-humanization/current",
    response_model=PostTranslationHumanizationCurrentResponse,
)
def get_current_post_translation_humanization(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostTranslationHumanizationCurrentResponse:
    report = db.get(Report, report_id)
    if (
        report is None
        or getattr(report, "deleted_at", None) is not None
        or report.user_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="not found")
    run = db.execute(
        select(HumanizationRun)
        .where(
            HumanizationRun.report_id == report_id,
            HumanizationRun.stage == 'post_translation',
            HumanizationRun.status == 'success',
        )
        .order_by(
            HumanizationRun.created_at.desc(),
            HumanizationRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail='post-translation humanization not found')
    policy = run.policy_json or {}
    return PostTranslationHumanizationCurrentResponse(
        run=run,
        translated_version_id=(
            uuid.UUID(policy["translated_version_id"])
            if policy.get("translated_version_id")
            else None
        ),
        output_version_id=(
            uuid.UUID(policy["output_version_id"])
            if policy.get("output_version_id")
            else None
        ),
    )
