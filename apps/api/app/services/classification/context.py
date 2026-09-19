"""M21 — Bounded context aggregation with per-source provenance."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report, ReportVersion


@dataclass(frozen=True)
class ContextChunk:
    location: str
    text: str


@dataclass
class ClassificationContext:
    project_id: uuid.UUID
    explicit_domain: str | None
    name: str
    chunks: list[ContextChunk] = field(default_factory=list)

    def chunks_starting_with(self, prefix: str) -> list[ContextChunk]:
        return [c for c in self.chunks if c.location.startswith(prefix)]

    def project_field(self, field_name: str) -> str:
        loc = f"project.{field_name}"
        for c in self.chunks:
            if c.location == loc:
                return c.text
        return ""


def _truncate(value: str | None, limit: int) -> str:
    if not value:
        return ""
    return value[:limit]


def _fetch_files(
    db: Session, *, project: Project, limit: int
) -> list[ProjectFile]:
    if limit <= 0:
        return []
    return list(
        db.execute(
            select(ProjectFile)
            .where(
                ProjectFile.project_id == project.id,
                ProjectFile.deleted_at.is_(None),
            )
            .order_by(ProjectFile.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def _fetch_reports(
    db: Session, *, project: Project, limit: int
) -> list[Report]:
    if limit <= 0:
        return []
    return list(
        db.execute(
            select(Report)
            .where(
                Report.project_id == project.id,
                Report.deleted_at.is_(None),
            )
            .order_by(Report.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def _fetch_top_versions(
    db: Session, *, report_ids: list[uuid.UUID], limit: int = 5
) -> list[ReportVersion]:
    if not report_ids or limit <= 0:
        return []
    return list(
        db.execute(
            select(ReportVersion)
            .where(ReportVersion.report_id.in_(report_ids))
            .order_by(ReportVersion.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def build_context(
    db: Session, *, project: Project
) -> ClassificationContext:
    settings = get_settings()
    chunks: list[ContextChunk] = []

    for loc, val in (
        ("project.name", project.name),
        ("project.description", project.description),
        ("project.research_objective", project.research_objective),
        (
            "project.research_questions",
            " ".join(str(q) for q in (project.research_questions or [])),
        ),
        (
            "project.hypotheses",
            " ".join(str(h) for h in (project.hypotheses or [])),
        ),
        ("project.scope", project.scope),
        ("project.constraints", project.constraints),
    ):
        truncated = _truncate(
            val, settings.classification_max_project_text
        )
        if truncated:
            chunks.append(ContextChunk(location=loc, text=truncated))

    files = _fetch_files(
        db, project=project,
        limit=settings.classification_max_files,
    )
    for f in files:
        if f.normalized_filename:
            chunks.append(
                ContextChunk(
                    location=f"file:{f.id}.name",
                    text=f.normalized_filename[:500],
                )
            )
        if f.extracted_text:
            t = _truncate(
                f.extracted_text,
                settings.classification_max_file_text,
            )
            if t:
                chunks.append(
                    ContextChunk(
                        location=f"file:{f.id}.text", text=t
                    )
                )

    reports = _fetch_reports(
        db, project=project,
        limit=settings.classification_max_reports,
    )
    for r in reports:
        if r.topic:
            chunks.append(
                ContextChunk(
                    location=f"report:{r.id}.topic",
                    text=_truncate(r.topic, 500),
                )
            )
        if r.domain:
            chunks.append(
                ContextChunk(
                    location=f"report:{r.id}.domain",
                    text=_truncate(r.domain, 200),
                )
            )

    report_ids = [r.id for r in reports]
    versions = _fetch_top_versions(db, report_ids=report_ids)
    for v in versions:
        if v.content:
            t = _truncate(
                v.content, settings.classification_max_file_text
            )
            if t:
                chunks.append(
                    ContextChunk(
                        location=f"report_version:{v.id}.content",
                        text=t,
                    )
                )

    return ClassificationContext(
        project_id=project.id,
        explicit_domain=project.domain,
        name=project.name,
        chunks=chunks,
    )


def compute_context_hash(ctx: ClassificationContext) -> str:
    """Hash the ACTUAL classifier inputs (ContextChunks).

    If two contexts have the same hash, classifiers will produce the
    same output, so we can skip re-classification.
    """
    h = hashlib.sha256()
    for c in sorted(ctx.chunks, key=lambda x: x.location):
        h.update(c.location.encode("utf-8"))
        h.update(b"\x00")
        h.update(c.text.encode("utf-8"))
        h.update(b"\x01")
    return h.hexdigest()[:32]
