"""Bridge project-file text into the existing Source/Chunk evidence path."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.report import Report
from app.db.models.source import Chunk, Source
from app.db.models.project_file import ProjectFile
from app.domain.text_chunking import WordTextChunker
from app.services.embedding_jobs import enqueue_source_embedding_job

_SOURCE_API = "project_file"


def sync_project_file_evidence(
    db: Session,
    *,
    project_file_id: uuid.UUID,
    user_id: uuid.UUID | None,
    report_id: uuid.UUID | None = None,
) -> int:
    """Materialize extracted project-file text as report-local evidence.

    Project files are project-scoped while Source is report-scoped. We
    therefore mirror one logical file into each active report in the
    project, using the project-file id as the stable external identity.
    """
    pf = db.get(ProjectFile, project_file_id)
    if pf is None or pf.deleted_at is not None:
        return 0
    text = (pf.extracted_text or "").strip()
    if not text:
        return 0

    settings = get_settings()
    chunker = WordTextChunker(
        target_words=settings.chunk_target_words,
        overlap_words=settings.chunk_overlap_words,
    )
    chunks = chunker.chunk(text)
    if not chunks:
        return 0

    report_stmt = select(Report).where(
        Report.project_id == pf.project_id,
        Report.deleted_at.is_(None),
    )
    if report_id is not None:
        report_stmt = report_stmt.where(Report.id == report_id)
    reports = list(db.execute(
        report_stmt.order_by(Report.created_at.asc(), Report.id.asc())
    ).scalars().all())

    synced = 0
    for report in reports:
        source = db.execute(
            select(Source).where(
                Source.report_id == report.id,
                Source.source_api == _SOURCE_API,
                Source.external_source_id == str(pf.id),
            ).limit(1)
        ).scalar_one_or_none()

        if source is None:
            source = Source(
                report_id=report.id,
                title=pf.original_filename,
                authors=None,
                year=None,
                doi=None,
                url=None,
                source_api=_SOURCE_API,
                external_source_id=str(pf.id),
                citation_count=None,
                abstract=None,
                full_text=text,
                status="full_text",
                content_hash=pf.sha256,
                content_type=pf.detected_mime_type or pf.client_mime_type,
                content_length=len(text.encode("utf-8")),
                extracted_at=pf.updated_at,
                extraction_pipeline_version=pf.extraction_pipeline_version,
                source_meta=_source_metadata(pf),
            )
            db.add(source)
            db.flush()
        else:
            source.title = pf.original_filename
            source.full_text = text
            source.status = "full_text"
            source.content_hash = pf.sha256
            source.content_type = pf.detected_mime_type or pf.client_mime_type
            source.content_length = len(text.encode("utf-8"))
            source.extracted_at = pf.updated_at
            source.extraction_pipeline_version = pf.extraction_pipeline_version
            source.source_meta = _source_metadata(pf)
            db.execute(delete(Chunk).where(Chunk.source_id == source.id))

        for chunk in chunks:
            db.add(Chunk(
                source_id=source.id,
                content=chunk.content,
                chunk_index=chunk.chunk_index,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                page_number=chunk.page_number,
                embedding_status="pending",
                chunk_meta={
                    "evidence_origin": "project_file",
                    "project_file_id": str(pf.id),
                    "file_kind": pf.file_kind,
                },
            ))
        db.flush()

        if user_id is not None:
            enqueue_source_embedding_job(
                db,
                user_id=user_id,
                report_id=report.id,
                source_id=source.id,
            )
        synced += 1

    db.commit()
    return synced


def _source_metadata(pf: ProjectFile) -> dict[str, Any]:
    return {
        "evidence_origin": "project_file",
        "project_file_id": str(pf.id),
        "filename": pf.original_filename,
        "normalized_filename": pf.normalized_filename,
        "file_kind": pf.file_kind,
        "sha256": pf.sha256,
        "storage_provider": pf.storage_provider,
    }


def sync_ready_project_files_for_report(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    files = list(db.execute(
        select(ProjectFile).where(
            ProjectFile.project_id == project_id,
            ProjectFile.deleted_at.is_(None),
            ProjectFile.extraction_status == "completed",
        ).order_by(ProjectFile.created_at.asc(), ProjectFile.id.asc())
    ).scalars().all())
    synced = 0
    for pf in files:
        synced += sync_project_file_evidence(
            db,
            project_file_id=pf.id,
            user_id=user_id,
            report_id=report_id,
        )
    return synced


__all__ = [
    "sync_project_file_evidence",
    "sync_ready_project_files_for_report",
]
