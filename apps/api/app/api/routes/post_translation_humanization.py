"""M17 — Post-translation humanization recovery routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
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
