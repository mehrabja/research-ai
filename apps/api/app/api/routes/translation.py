"""M16 — Translation routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.schemas.translation_current import TranslationCurrentResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.services import translation_jobs as translation_jobs_service
from app.services.translation_profile import (
    get_current_translation_profile_id,
)

router = APIRouter(prefix="/reports", tags=["translation"])


class TranslationEnqueueRequest(BaseModel):
    source_version_id: uuid.UUID
    target_language: str


@router.post(
    "/{report_id}/translation/enqueue",
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_translation(
    report_id: uuid.UUID,
    body: TranslationEnqueueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        job_id = translation_jobs_service.enqueue_translation_job(
            db=db,
            user_id=current_user.id,
            report_id=report_id,
            source_version_id=body.source_version_id,
            target_language=body.target_language,
            profile_id=get_current_translation_profile_id(),
        )
        db.commit()
    except translation_jobs_service.TranslationEnqueueOwnershipError:
        db.rollback()
        raise HTTPException(status_code=404, detail="not found") from None
    except translation_jobs_service.TranslationEnqueueStateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"job_id": str(job_id), "status": "queued"}

@router.get(
    "/{report_id}/translation/current",
    response_model=TranslationCurrentResponse,
)
def get_current_translation(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationCurrentResponse:
    report = reports_service.get_report(
        db, user_id=current_user.id, report_id=report_id
    )
    run = db.execute(
        select(TranslationRun)
        .where(
            TranslationRun.report_id == report.id,
            TranslationRun.status == "success",
        )
        .order_by(TranslationRun.created_at.desc(), TranslationRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="translation not found")
    version = db.execute(
        select(TranslationVersion)
        .where(TranslationVersion.translation_run_id == run.id)
        .order_by(TranslationVersion.created_at.desc(), TranslationVersion.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="translation version not found")
    return TranslationCurrentResponse(
        run_id=run.id, translation_version_id=version.id,
        source_version_id=run.source_version_id, source_lang=run.source_lang,
        target_lang=run.target_lang, provider=run.provider, status=run.status,
        completed_at=run.completed_at, content=version.content,
        preservation_check_status=version.preservation_check_status,
        preservation_details=version.preservation_details,
    )
