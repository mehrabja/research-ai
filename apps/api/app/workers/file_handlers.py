"""M19 — Worker handler for ``file_extract`` jobs.

Retry semantics:

  - Worker raises on failure. Job queue's ``fail_job`` decides whether
    to retry based on attempt_count vs max_attempts.
  - While retrying (non-final attempt), the file stays in PROCESSING
    so the next attempt's ``mark_processing`` is idempotent.
  - Only when the current attempt is final (attempt_count == max_attempts)
    does the worker mark the file FAILED.
"""
from __future__ import annotations

import logging
import uuid
from typing import cast

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import StorageUnavailable
from app.db.models.jobs import Job
from app.db.models.project_file import ProjectFile
from app.domain.file import FileKind
from app.services import files as files_service
from app.services.file_extraction import (
    EXTRACTION_PIPELINE_VERSION,
    extract_bytes,
)
from app.services.file_storage import get_storage_provider

logger = logging.getLogger(__name__)


def _read_bounded(provider, key: str, max_bytes: int) -> bytes:
    """Read whole object into memory but enforce cap defensively."""
    buf = bytearray()
    for chunk in provider.open(key=key):
        if len(buf) + len(chunk) > max_bytes:
            raise StorageUnavailable("stored object exceeds configured cap")
        buf.extend(chunk)
    return bytes(buf)


def handle_file_extract(db: Session, job: Job) -> None:
    file_id_raw = job.payload.get("file_id")
    if not file_id_raw:
        raise ValueError("file_extract payload missing file_id")
    file_id = uuid.UUID(str(file_id_raw))

    # Job.user_id is declared as ``Mapped[PGUUID | None]`` (existing M10
    # pattern, kept for consistency). Narrow it to ``uuid.UUID | None``
    # at the M10 ↔ M19 boundary so service signatures stay idiomatic.
    job_user_id = cast(uuid.UUID | None, job.user_id)

    if not files_service.mark_processing(
        db, file_id=file_id, user_id=job_user_id
    ):
        return

    pf = db.get(ProjectFile, file_id)
    if pf is None:
        return

    try:
        settings = get_settings()
        provider = get_storage_provider()
        content = _read_bounded(
            provider, pf.storage_key, settings.document_max_bytes
        )
        result = extract_bytes(
            content=content,
            kind=FileKind(pf.file_kind),
            mime=pf.detected_mime_type or pf.client_mime_type,
        )
        if result.error is not None:
            raise RuntimeError(f"extraction failed: {result.error}")
    except Exception as exc:  # noqa: BLE001
        # Contract with M10 (`services/jobs.py::claim_job`):
        # attempt_count is incremented BEFORE handler runs. The
        # final attempt therefore satisfies
        # ``attempt_count >= max_attempts``. Only on this attempt do
        # we mark the file FAILED.
        is_final = job.attempt_count >= job.max_attempts
        if is_final:
            files_service.mark_extraction_failed(
                db,
                file_id=file_id,
                user_id=job_user_id,
                error=str(exc),
            )
        else:
            logger.info(
                "file_extract attempt %d/%d failed for file_id=%s; "
                "retry pending",
                job.attempt_count,
                job.max_attempts,
                file_id,
            )
        raise

    if result.supported:
        files_service.apply_extraction_result(
            db,
            file_id=file_id,
            user_id=job_user_id,
            text=result.text,
            pipeline_version=EXTRACTION_PIPELINE_VERSION,
            meta=result.meta,
            extraction_status="completed",
        )
    else:
        files_service.apply_extraction_result(
            db,
            file_id=file_id,
            user_id=job_user_id,
            text=None,
            pipeline_version=EXTRACTION_PIPELINE_VERSION,
            meta=None,
            extraction_status="not_supported",
        )
