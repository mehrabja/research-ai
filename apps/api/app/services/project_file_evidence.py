from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.project_file import ProjectFile
from app.db.models.report import Report
from app.db.models.source import Chunk, Source
from app.schemas.evidence import EvidenceKind, EvidenceRecord
from app.services.artifact_evidence import sync_ready_project_files_for_report
from app.services.evidence_contract import from_chunk, from_project_file
from app.services.projects import get_project
from app.services.reports import get_report


def list_project_file_evidence(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> tuple[list[dict[str, Any]], int]:
    get_project(db, user_id=user_id, project_id=project_id)

    files, total = _list_active_files(db, project_id=project_id)
    file_ids = [pf.id for pf in files]

    source_map: dict[
        str,
        list[tuple[uuid.UUID, uuid.UUID, int, datetime]],
    ] = defaultdict(list)

    if file_ids:
        query_rows = db.execute(
            select(
                Source.id,
                Source.external_source_id,
                Source.report_id,
                Source.updated_at,
                func.count(Chunk.id).label("chunk_count"),
            )
            .outerjoin(Chunk, Chunk.source_id == Source.id)
            .where(
                Source.source_api == "project_file",
                Source.external_source_id.in_(
                    [str(fid) for fid in file_ids]
                ),
            )
            .group_by(
                Source.id,
                Source.external_source_id,
                Source.report_id,
                Source.updated_at,
            )
        ).all()

        for source_id, external_id, report_id, updated_at, chunk_count in query_rows:
            if external_id:
                source_map[external_id].append(
                    (
                        source_id,
                        report_id,
                        int(chunk_count),
                        updated_at,
                    )
                )

    result: list[dict[str, Any]] = []
    for pf in files:
        source_rows = source_map.get(str(pf.id), [])
        source_ids = [row[0] for row in source_rows]
        report_ids = sorted(
            {row[1] for row in source_rows},
            key=str,
        )
        chunk_count = sum(row[2] for row in source_rows)
        last_synced_at = max(
            (row[3] for row in source_rows),
            default=None,
        )

        if pf.extraction_status == "completed":
            evidence_status = "synced" if source_rows else "awaiting_report"
        elif pf.extraction_status in ("failed", "not_supported"):
            evidence_status = "unavailable"
        else:
            evidence_status = "processing"

        result.append(
            {
                "file_id": pf.id,
                "project_id": project_id,
                "filename": pf.original_filename,
                "file_kind": pf.file_kind,
                "extraction_status": pf.extraction_status,
                "evidence_status": evidence_status,
                "source_count": len(source_ids),
                "chunk_count": chunk_count,
                "source_ids": source_ids,
                "report_ids": report_ids,
                "last_synced_at": last_synced_at,
            }
        )

    return result, total


def sync_project_file_evidence_for_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
) -> int:
    get_project(db, user_id=user_id, project_id=project_id)
    report = get_report(db, user_id=user_id, report_id=report_id)
    if report.project_id != project_id:
        from app.core.exceptions import ProjectNotFound
        raise ProjectNotFound()

    return sync_ready_project_files_for_report(
        db,
        project_id=project_id,
        report_id=report_id,
        user_id=user_id,
    )


def _list_active_files(
    db: Session,
    *,
    project_id: uuid.UUID,
) -> tuple[list[ProjectFile], int]:
    base = select(ProjectFile).where(
        ProjectFile.project_id == project_id,
        ProjectFile.deleted_at.is_(None),
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    files = list(
        db.execute(
            base.order_by(
                ProjectFile.created_at.desc(),
                ProjectFile.id.asc(),
            )
        ).scalars().all()
    )
    return files, total


def list_canonical_project_evidence(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    kind: EvidenceKind | None = None,
    file_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[EvidenceRecord], int]:
    """List canonical evidence records visible in a project."""
    get_project(db, user_id=user_id, project_id=project_id)

    if file_id is not None:
        file = db.execute(
            select(ProjectFile).where(
                ProjectFile.id == file_id,
                ProjectFile.project_id == project_id,
                ProjectFile.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if file is None:
            from app.core.exceptions import FileNotFound
            raise FileNotFound()

    files: list[EvidenceRecord] = []
    if kind in (None, "project_file"):
        stmt = select(ProjectFile).where(
            ProjectFile.project_id == project_id,
            ProjectFile.deleted_at.is_(None),
        )
        if file_id is not None:
            stmt = stmt.where(ProjectFile.id == file_id)
        rows = list(
            db.execute(
                stmt.order_by(
                    ProjectFile.created_at.asc(),
                    ProjectFile.id.asc(),
                )
            ).scalars().all()
        )
        files = [from_project_file(row) for row in rows]

    chunks: list[EvidenceRecord] = []
    if kind in (None, "retrieval_chunk"):
        report_ids_stmt = select(Report.id).where(
            Report.project_id == project_id
        )
        stmt = (
            select(Chunk)
            .join(Source, Chunk.source_id == Source.id)
            .where(
                Source.report_id.in_(report_ids_stmt),
                Source.source_api == "project_file",
            )
        )
        if file_id is not None:
            stmt = stmt.where(
                Source.external_source_id == str(file_id)
            )
        rows = list(
            db.execute(
                stmt.order_by(Chunk.created_at.asc(), Chunk.id.asc())
            ).scalars().all()
        )
        chunks = [from_chunk(row) for row in rows]

    merged = sorted(
        files + chunks,
        key=lambda item: (
            item.created_at is None,
            item.created_at,
            item.evidence_key,
        ),
    )
    total = len(merged)
    return merged[offset : offset + limit], total
