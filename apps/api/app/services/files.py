"""M19 + M20 + M21 — ProjectFile service.

M19 owns upload, read, list, soft-delete, dedup, extraction enqueue.
M20 adds intelligence dispatch (code_analyze / data_profile) after
upload succeeds, plus re-dispatch after extraction completion.
M21 adds project-level research classification dispatch and re-dispatch
after any file lifecycle change that alters classifier context.

All state changes go through ``can_transition_file``.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    DuplicateFile,
    FileNotFound,
    FileTooLarge,
    InvalidFileName,
    InvalidFileStatusTransition,
    ProjectArchivedForUpload,
    ProjectNotFound,
    StorageUnavailable,
)
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.domain.file import (
    ExtractionStatus,
    FileKind,
    FileStatus,
    InvalidFileNameError,
    can_transition_file,
    classify,
    detect_mime_from_bytes,
    extension_of,
    initial_extraction_status,
    sanitize_filename,
    storage_key_for,
)
from app.domain.project import EDITABLE_PROJECT_STATUSES
from app.services import entitlements as entitlements_service
from app.services import jobs as jobs_service
from app.services.file_storage import get_storage_provider

logger = logging.getLogger(__name__)

_DUPLICATE_CONSTRAINT = "ux_project_files_project_sha256_active"
# 4096: enough for OOXML markers ([Content_Types].xml lives within
# the first 4KiB of every docx/xlsx/pptx archive local file header).
_HEAD_PROBE_BYTES = 4096


# ---------------------------------------------------------------------------
# M21 — classification re-enqueue helper (best-effort)
# ---------------------------------------------------------------------------
def _re_enqueue_classification(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    reason: str,
) -> None:
    """Best-effort classification re-enqueue. Never raises."""
    try:
        from app.services.classification.orchestrator import (
            enqueue_recompute_if_enabled,
        )
        enqueue_recompute_if_enabled(
            db, project_id=project_id, user_id=user_id
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "classification re-enqueue failed reason=%s project_id=%s",
            reason,
            project_id,
        )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
def _emit_event(
    db: Session,
    *,
    project_file_id: uuid.UUID,
    user_id: uuid.UUID | None,
    event_type: str,
    event_meta: dict[str, Any] | None = None,
) -> None:
    db.add(
        ProjectFileEvent(
            project_file_id=project_file_id,
            user_id=user_id,
            event_type=event_type,
            event_meta=event_meta or {},
        )
    )


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------
def get_file(
    db: Session, *, user_id: uuid.UUID, file_id: uuid.UUID
) -> ProjectFile:
    pf = db.execute(
        select(ProjectFile)
        .join(Project, Project.id == ProjectFile.project_id)
        .where(
            ProjectFile.id == file_id,
            Project.user_id == user_id,
        )
    ).scalar_one_or_none()
    if pf is None:
        raise FileNotFound()
    return pf


def _read_head(provider, storage_key: str, max_bytes: int) -> bytes:
    buf = bytearray()
    for chunk in provider.open(key=storage_key):
        need = max_bytes - len(buf)
        if need <= 0:
            break
        buf.extend(chunk[:need])
        if len(buf) >= max_bytes:
            break
    return bytes(buf)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
def upload_file(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    original_filename: str,
    client_mime: str | None,
    upload_stream: Iterator[bytes],
) -> ProjectFile:
    """Upload a file. Commits internally; caller does not manage txn.

    There is no ``commit=False`` mode on purpose: storage writes and
    dedup constraints cannot be rolled back atomically with the DB,
    and the follow-up job enqueue always commits.
    """
    settings = get_settings()

    # 1. Project ownership + editable.
    project = db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == user_id
        )
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFound()
    if project.status not in EDITABLE_PROJECT_STATUSES:
        raise ProjectArchivedForUpload()

    # 2. Filename (domain error -> AppError boundary).
    try:
        normalized = sanitize_filename(
            original_filename,
            max_length=settings.file_max_filename_length,
        )
    except InvalidFileNameError as exc:
        raise InvalidFileName(str(exc)) from exc
    ext = extension_of(normalized)

    file_id = uuid.uuid4()
    storage_key = storage_key_for(project_id=project_id, file_id=file_id)

    # 3. Stream to storage with hashing + size enforcement.
    hasher = hashlib.sha256()
    total = 0

    def _hashing_stream() -> Iterator[bytes]:
        nonlocal total
        for chunk in upload_stream:
            if not chunk:
                continue
            total += len(chunk)
            if total > settings.document_max_bytes:
                raise FileTooLarge()
            hasher.update(chunk)
            yield chunk

    provider = get_storage_provider()
    provider.put_stream(key=storage_key, chunks=_hashing_stream())

    # Everything from here until commit is inside a single cleanup
    # boundary. Any failure (I/O on read-back, MIME probe, DB,
    # event emission) must remove the storage object.
    try:
        sha256 = hasher.hexdigest()

        entitlements_service.check_and_reserve_storage_bytes(
            db,
            workspace_id=project.workspace_id,
            additional_bytes=total,
        )

        head = _read_head(provider, storage_key, _HEAD_PROBE_BYTES)
        detected_mime = detect_mime_from_bytes(head)

        kind: FileKind = classify(
            detected_mime=detected_mime,
            client_mime=client_mime,
            extension=ext,
        )

        initial_extraction = initial_extraction_status(
            kind,
            detected_mime=detected_mime,
            client_mime=client_mime,
        )

        pf = ProjectFile(
            id=file_id,
            project_id=project_id,
            uploaded_by=user_id,
            original_filename=original_filename,
            normalized_filename=normalized,
            extension=ext,
            storage_key=storage_key,
            storage_provider=settings.file_storage_backend,
            size_bytes=total,
            sha256=sha256,
            client_mime_type=client_mime,
            detected_mime_type=detected_mime,
            file_kind=kind.value,
            status=FileStatus.UPLOADED.value,
            extraction_status=initial_extraction.value,
        )
        db.add(pf)
        db.flush()
        _emit_event(
            db,
            project_file_id=pf.id,
            user_id=user_id,
            event_type="file_uploaded",
            event_meta={
                "filename": normalized,
                "kind": kind.value,
                "size_bytes": total,
                "detected_mime": detected_mime,
            },
        )
        db.commit()
        db.refresh(pf)
    except IntegrityError as exc:
        db.rollback()
        _best_effort_delete(storage_key)
        if _constraint_name(exc) == _DUPLICATE_CONSTRAINT:
            raise DuplicateFile() from exc
        raise
    except BaseException:
        db.rollback()
        _best_effort_delete(storage_key)
        raise

    # 4. M19 — file extraction enqueue.
    if initial_extraction is ExtractionStatus.QUEUED:
        try:
            jobs_service.enqueue_job(
                db,
                job_type="file_extract",
                payload={"file_id": str(pf.id)},
                idempotency_key=f"file_extract:{pf.id}",
                project_file_id=pf.id,
                user_id=user_id,
                max_attempts=settings.file_extraction_max_attempts,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "file_extract enqueue failed for file_id=%s", pf.id
            )
            pf.extraction_status = ExtractionStatus.NOT_STARTED.value
            db.commit()

    # 5. M20 — code/data intelligence dispatch.
    try:
        from app.services.intelligence_dispatch import (
            enqueue_intelligence_for_file,
        )
        enqueue_intelligence_for_file(db, pf=pf, user_id=user_id)
    except Exception:  # noqa: BLE001
        logger.exception(
            "intelligence enqueue failed for file_id=%s", pf.id
        )

    # 6. M21 — project classification dispatch (idempotent per hash).
    _re_enqueue_classification(
        db,
        project_id=project_id,
        user_id=user_id,
        reason="file_upload",
    )

    return pf


def _best_effort_delete(storage_key: str) -> None:
    try:
        get_storage_provider().delete(key=storage_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "storage cleanup failed for key=%s: %s", storage_key, exc
        )


def _constraint_name(exc: IntegrityError) -> str | None:
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    return getattr(diag, "constraint_name", None)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
def list_files(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    status: str | None = None,
    file_kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ProjectFile], int]:
    project = db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == user_id
        )
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFound()

    base = select(ProjectFile).where(
        ProjectFile.project_id == project_id,
        ProjectFile.deleted_at.is_(None),
    )
    if status:
        base = base.where(ProjectFile.status == status)
    if file_kind:
        base = base.where(ProjectFile.file_kind == file_kind)

    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = (
        db.execute(
            base.order_by(ProjectFile.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(rows), total


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
def open_content(
    db: Session, *, user_id: uuid.UUID, file_id: uuid.UUID
) -> tuple[ProjectFile, Iterator[bytes]]:
    pf = get_file(db, user_id=user_id, file_id=file_id)
    if pf.deleted_at is not None:
        raise FileNotFound()
    provider = get_storage_provider()
    if not provider.exists(key=pf.storage_key):
        raise StorageUnavailable("file object missing from storage")
    return pf, provider.open(key=pf.storage_key)


# ---------------------------------------------------------------------------
# Delete (soft)
# ---------------------------------------------------------------------------
def delete_file(
    db: Session, *, user_id: uuid.UUID, file_id: uuid.UUID
) -> ProjectFile:
    pf = get_file(db, user_id=user_id, file_id=file_id)
    if pf.status == FileStatus.DELETED.value:
        return pf

    if not can_transition_file(pf.status, FileStatus.DELETED.value):
        raise InvalidFileStatusTransition(
            f"cannot delete file in status {pf.status!r}"
        )

    project_id = pf.project_id

    pf.status = FileStatus.DELETED.value
    pf.deleted_at = datetime.now(UTC)
    _emit_event(
        db,
        project_file_id=pf.id,
        user_id=user_id,
        event_type="file_deleted",
        event_meta={},
    )
    db.commit()
    db.refresh(pf)

    _best_effort_delete(pf.storage_key)

    # M21 — file deletion removes a context source.
    _re_enqueue_classification(
        db,
        project_id=project_id,
        user_id=user_id,
        reason="file_delete",
    )

    return pf


# ---------------------------------------------------------------------------
# Worker hooks
# ---------------------------------------------------------------------------
def mark_processing(
    db: Session, *, file_id: uuid.UUID, user_id: uuid.UUID | None
) -> bool:
    """Transition uploaded -> processing, under row lock.

    READY -> PROCESSING is intentionally not allowed by the domain
    (extraction must not re-run automatically once READY).

    Idempotent: if already processing (retry attempt), returns True
    without re-emitting the event.
    """
    pf = db.execute(
        select(ProjectFile)
        .where(ProjectFile.id == file_id)
        .with_for_update()
    ).scalar_one_or_none()
    if pf is None or pf.status == FileStatus.DELETED.value:
        db.rollback()
        return False
    if pf.status == FileStatus.PROCESSING.value:
        db.commit()
        return True
    if not can_transition_file(pf.status, FileStatus.PROCESSING.value):
        db.rollback()
        return False
    pf.status = FileStatus.PROCESSING.value
    pf.extraction_status = ExtractionStatus.PROCESSING.value
    _emit_event(
        db,
        project_file_id=pf.id,
        user_id=user_id,
        event_type="file_processing_started",
        event_meta={},
    )
    db.commit()
    return True


def apply_extraction_result(
    db: Session,
    *,
    file_id: uuid.UUID,
    user_id: uuid.UUID | None,
    text: str | None,
    pipeline_version: str,
    meta: dict[str, Any] | None,
    extraction_status: str,
) -> None:
    pf = db.execute(
        select(ProjectFile)
        .where(ProjectFile.id == file_id)
        .with_for_update()
    ).scalar_one_or_none()
    if pf is None or pf.status == FileStatus.DELETED.value:
        db.rollback()
        return
    if pf.status != FileStatus.PROCESSING.value:
        db.rollback()
        return

    if extraction_status == ExtractionStatus.COMPLETED.value:
        pf.extracted_text = text
        pf.extraction_status = ExtractionStatus.COMPLETED.value
    else:
        pf.extraction_status = ExtractionStatus.NOT_SUPPORTED.value

    if meta:
        pf.file_meta = {**(pf.file_meta or {}), **meta}
    pf.extraction_pipeline_version = pipeline_version
    pf.status = FileStatus.READY.value
    pf.extraction_error = None

    _emit_event(
        db,
        project_file_id=pf.id,
        user_id=user_id,
        event_type="file_processing_completed",
        event_meta={
            "extraction_status": pf.extraction_status,
            "chars": len(text) if text else 0,
        },
    )
    db.commit()

    # M21 — extraction completion changes classifier inputs.
    _re_enqueue_classification(
        db,
        project_id=pf.project_id,
        user_id=user_id,
        reason="extraction_completed",
    )


def mark_extraction_failed(
    db: Session,
    *,
    file_id: uuid.UUID,
    user_id: uuid.UUID | None,
    error: str,
) -> None:
    """Terminal failure — only called when retries are exhausted."""
    pf = db.execute(
        select(ProjectFile)
        .where(ProjectFile.id == file_id)
        .with_for_update()
    ).scalar_one_or_none()
    if pf is None or pf.status == FileStatus.DELETED.value:
        db.rollback()
        return
    if not can_transition_file(pf.status, FileStatus.FAILED.value):
        db.rollback()
        return
    pf.status = FileStatus.FAILED.value
    pf.extraction_status = ExtractionStatus.FAILED.value
    pf.extraction_error = error[:500]
    _emit_event(
        db,
        project_file_id=pf.id,
        user_id=user_id,
        event_type="file_processing_failed",
        event_meta={"error": error[:200]},
    )
    db.commit()

    # M21 — extraction failure also changes context.
    _re_enqueue_classification(
        db,
        project_id=pf.project_id,
        user_id=user_id,
        reason="extraction_failed",
    )
