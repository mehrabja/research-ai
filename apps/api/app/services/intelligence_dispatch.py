"""M20 — Dispatch helper for enqueuing intelligence jobs."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.project_file import ProjectFile
from app.domain.code_intelligence import (
    Language,
    LanguageSupport,
    detect_language,
    language_support,
)
from app.domain.data_intelligence import (
    DataFormat,
    detect_data_format,
)
from app.services import jobs as jobs_service

logger = logging.getLogger(__name__)


def enqueue_intelligence_for_file(
    db: Session, *, pf: ProjectFile, user_id: uuid.UUID
) -> None:
    if pf.deleted_at is not None:
        return
    settings = get_settings()

    lang = detect_language(pf.extension)
    if (
        lang is not Language.UNKNOWN
        and language_support(lang) is not LanguageSupport.UNSUPPORTED
    ):
        try:
            jobs_service.enqueue_job(
                db,
                job_type="code_analyze",
                payload={"file_id": str(pf.id)},
                idempotency_key=f"code_analyze:{pf.id}",
                project_file_id=pf.id,
                user_id=user_id,
                max_attempts=settings.file_extraction_max_attempts,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "code_analyze enqueue failed for file_id=%s", pf.id
            )
        return

    fmt = detect_data_format(
        extension=pf.extension,
        mime=pf.detected_mime_type or pf.client_mime_type,
    )
    if fmt is not DataFormat.UNKNOWN:
        try:
            jobs_service.enqueue_job(
                db,
                job_type="data_profile",
                payload={"file_id": str(pf.id)},
                idempotency_key=f"data_profile:{pf.id}",
                project_file_id=pf.id,
                user_id=user_id,
                max_attempts=settings.file_extraction_max_attempts,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "data_profile enqueue failed for file_id=%s", pf.id
            )
