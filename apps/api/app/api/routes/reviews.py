"""M15 — Pre-translation review routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.reviews import (
    PreTranslationApproveRequest,
    PreTranslationEditRequest,
    PreTranslationRejectRequest,
    PreTranslationRequestChangesRequest,
    PreTranslationReviewResponse,
)
from app.services import reviews as reviews_service

router = APIRouter(prefix="/reports", tags=["reviews"])


def _to_response(data: dict) -> PreTranslationReviewResponse:
    return PreTranslationReviewResponse(**data)


@router.get(
    "/{report_id}/review/pre-translation",
    response_model=PreTranslationReviewResponse,
)
def get_pre_translation_review(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreTranslationReviewResponse:
    data = reviews_service.get_pre_translation_review(
        db, user_id=current_user.id, report_id=report_id
    )
    return _to_response(data)


@router.post(
    "/{report_id}/review/pre-translation/edit",
    response_model=PreTranslationReviewResponse,
)
def edit_pre_translation_review(
    report_id: uuid.UUID,
    body: PreTranslationEditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreTranslationReviewResponse:
    reviews_service.edit_pre_translation_review(
        db,
        user_id=current_user.id,
        report_id=report_id,
        version_id=body.version_id,
        content=body.content,
        notes=body.notes,
    )
    data = reviews_service.get_pre_translation_review(
        db, user_id=current_user.id, report_id=report_id
    )
    return _to_response(data)


@router.post(
    "/{report_id}/review/pre-translation/approve",
    response_model=PreTranslationReviewResponse,
)
def approve_pre_translation_review(
    report_id: uuid.UUID,
    body: PreTranslationApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreTranslationReviewResponse:
    reviews_service.approve_pre_translation_review(
        db,
        user_id=current_user.id,
        report_id=report_id,
        version_id=body.version_id,
    )
    data = reviews_service.get_pre_translation_review(
        db, user_id=current_user.id, report_id=report_id
    )
    return _to_response(data)


@router.post(
    "/{report_id}/review/pre-translation/request-changes",
    response_model=PreTranslationReviewResponse,
)
def request_changes_pre_translation_review(
    report_id: uuid.UUID,
    body: PreTranslationRequestChangesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreTranslationReviewResponse:
    reviews_service.request_changes_pre_translation_review(
        db,
        user_id=current_user.id,
        report_id=report_id,
        version_id=body.version_id,
        notes=body.notes,
    )
    data = reviews_service.get_pre_translation_review(
        db, user_id=current_user.id, report_id=report_id
    )
    return _to_response(data)


@router.post(
    "/{report_id}/review/pre-translation/reject",
    response_model=PreTranslationReviewResponse,
)
def reject_pre_translation_review(
    report_id: uuid.UUID,
    body: PreTranslationRejectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreTranslationReviewResponse:
    reviews_service.reject_pre_translation_review(
        db,
        user_id=current_user.id,
        report_id=report_id,
        version_id=body.version_id,
        notes=body.notes,
    )
    data = reviews_service.get_pre_translation_review(
        db, user_id=current_user.id, report_id=report_id
    )
    return _to_response(data)
