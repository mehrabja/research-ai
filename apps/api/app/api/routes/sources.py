"""Source extraction routes.

POST /api/v1/reports/{report_id}/sources/{source_id}/extract

Fetch, extract, normalize, hash, chunk, and persist a source
document. Emits a ``source_extracted`` audit event atomically.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.source_extraction import SourceExtractionResponse
from app.services import extraction as extraction_service

router = APIRouter(
    prefix="/reports",
    tags=["sources"],
)


@router.post(
    "/{report_id}/sources/{source_id}/extract",
    response_model=SourceExtractionResponse,
    summary="Fetch, extract, normalize, and chunk a source document",
)
def extract_source(
    report_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceExtractionResponse:
    result = extraction_service.extract_source(
        db,
        user_id=current_user.id,
        report_id=report_id,
        source_id=source_id,
    )
    return SourceExtractionResponse(
        source_id=result.source_id,
        status=result.status,
        content_hash=result.content_hash,
        chunk_count=result.chunk_count,
        content_type=result.content_type,
        content_length=result.content_length,
        extracted_at=result.extracted_at,
        pipeline_version=result.pipeline_version,
    )
