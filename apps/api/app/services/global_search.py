"""Workspace-scoped global search across core research resources."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.membership import WorkspaceMembership
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report
from app.db.models.source import Source


@dataclass(frozen=True)
class SearchItem:
    type: str
    id: uuid.UUID
    title: str
    snippet: str | None
    workspace_id: uuid.UUID | None
    project_id: uuid.UUID | None
    report_id: uuid.UUID | None


def _workspace_ids(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
) -> set[uuid.UUID]:
    stmt = select(WorkspaceMembership.workspace_id).where(
        WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.status == "active",
    )
    if workspace_id is not None:
        stmt = stmt.where(WorkspaceMembership.workspace_id == workspace_id)
    return set(db.execute(stmt).scalars().all())


def global_search(
    db: Session,
    *,
    user_id: uuid.UUID,
    query: str,
    workspace_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SearchItem], int]:
    q = query.strip()
    if not q:
        return [], 0

    workspace_ids = _workspace_ids(
        db,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    if workspace_id is not None and workspace_id not in workspace_ids:
        return [], 0

    pattern = f"%{q}%"
    items: list[SearchItem] = []

    project_stmt = select(Project).where(
        Project.workspace_id.in_(workspace_ids),
        or_(
            Project.name.ilike(pattern),
            Project.description.ilike(pattern),
            Project.research_objective.ilike(pattern),
            Project.scope.ilike(pattern),
        ),
    )
    for row in db.execute(project_stmt).scalars().all():
        items.append(
            SearchItem(
                type="project",
                id=row.id,
                title=row.name,
                snippet=row.description or row.research_objective,
                workspace_id=row.workspace_id,
                project_id=row.id,
                report_id=None,
            )
        )

    report_stmt = (
        select(Report, Project.workspace_id)
        .outerjoin(Project, Project.id == Report.project_id)
        .where(
            or_(
                Report.user_id == user_id,
                Project.workspace_id.in_(workspace_ids),
            ),
            or_(
                Report.topic.ilike(pattern),
                Report.domain.ilike(pattern),
            ),
        )
    )
    if workspace_id is not None:
        report_stmt = report_stmt.where(Project.workspace_id == workspace_id)
    for row, ws_id in db.execute(report_stmt).all():
        items.append(
            SearchItem(
                type="report",
                id=row.id,
                title=row.topic,
                snippet=row.domain,
                workspace_id=ws_id,
                project_id=row.project_id,
                report_id=row.id,
            )
        )

    source_stmt = (
        select(Source, Project.workspace_id, Project.id)
        .join(Report, Report.id == Source.report_id)
        .outerjoin(Project, Project.id == Report.project_id)
        .where(
            or_(
                Report.user_id == user_id,
                Project.workspace_id.in_(workspace_ids),
            ),
            or_(
                Source.title.ilike(pattern),
                Source.doi.ilike(pattern),
                Source.url.ilike(pattern),
                Source.abstract.ilike(pattern),
            ),
        )
    )
    if workspace_id is not None:
        source_stmt = source_stmt.where(Project.workspace_id == workspace_id)
    for row, ws_id, project_id in db.execute(source_stmt).all():
        items.append(
            SearchItem(
                type="source",
                id=row.id,
                title=row.title,
                snippet=row.abstract,
                workspace_id=ws_id,
                project_id=project_id,
                report_id=row.report_id,
            )
        )

    file_stmt = (
        select(ProjectFile, Project.workspace_id)
        .join(Project, Project.id == ProjectFile.project_id)
        .where(
            Project.workspace_id.in_(workspace_ids),
            ProjectFile.deleted_at.is_(None),
            or_(
                ProjectFile.original_filename.ilike(pattern),
                ProjectFile.normalized_filename.ilike(pattern),
                ProjectFile.extracted_text.ilike(pattern),
            ),
        )
    )
    for row, ws_id in db.execute(file_stmt).all():
        items.append(
            SearchItem(
                type="file",
                id=row.id,
                title=row.original_filename,
                snippet=(row.extracted_text or "")[:500] or None,
                workspace_id=ws_id,
                project_id=row.project_id,
                report_id=None,
            )
        )

    items.sort(key=lambda x: (x.title.lower(), str(x.id)))
    total = len(items)
    return items[offset: offset + limit], total
