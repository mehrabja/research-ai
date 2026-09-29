from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report
from app.db.models.source import Source
from app.services.usage_contract import ProviderUsage, record_provider_usage
from app.services.workspaces import get_workspace_for_user


def search_workspace(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    limit: int = 20,
) -> tuple[list[dict], int]:
    get_workspace_for_user(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    q = query.strip()
    if len(q) < 2:
        return [], 0
    pattern = f"%{q}%"
    per_type = min(100, max(10, limit * 2))
    items: list[dict] = []

    projects = list(
        db.execute(
            select(Project).where(
                Project.workspace_id == workspace_id,
                or_(
                    Project.name.ilike(pattern),
                    Project.description.ilike(pattern),
                    Project.domain.ilike(pattern),
                ),
            )
            .order_by(Project.updated_at.desc())
            .limit(per_type)
        ).scalars()
    )
    items.extend(
        {
            "id": p.id,
            "resource_type": "project",
            "title": p.name,
            "snippet": p.description,
            "updated_at": p.updated_at,
            "project_id": p.id,
            "report_id": None,
        }
        for p in projects
    )

    reports = list(
        db.execute(
            select(Report)
            .join(Project, Project.id == Report.project_id)
            .where(
                Project.workspace_id == workspace_id,
                or_(
                    Report.topic.ilike(pattern),
                    Report.domain.ilike(pattern),
                ),
                Report.deleted_at.is_(None),
            )
            .order_by(Report.updated_at.desc())
            .limit(per_type)
        ).scalars()
    )
    items.extend(
        {
            "id": r.id,
            "resource_type": "report",
            "title": r.topic,
            "snippet": r.domain,
            "updated_at": r.updated_at,
            "project_id": r.project_id,
            "report_id": r.id,
        }
        for r in reports
    )

    source_rows = list(
        db.execute(
            select(Source, Project.id)
            .join(Report, Report.id == Source.report_id)
            .join(Project, Project.id == Report.project_id)
            .where(
                Project.workspace_id == workspace_id,
                or_(
                    Source.title.ilike(pattern),
                    Source.doi.ilike(pattern),
                    Source.url.ilike(pattern),
                    Source.abstract.ilike(pattern),
                    Source.full_text.ilike(pattern),
                ),
            )
            .order_by(Source.updated_at.desc())
            .limit(per_type)
        ).all()
    )
    items.extend(
        {
            "id": s.id,
            "resource_type": "source",
            "title": s.title,
            "snippet": s.doi or s.url,
            "updated_at": s.updated_at,
            "project_id": project_id,
            "report_id": s.report_id,
        }
        for s, project_id in source_rows
    )

    project_files = list(
        db.execute(
            select(ProjectFile)
            .join(Project, Project.id == ProjectFile.project_id)
            .where(
                Project.workspace_id == workspace_id,
                ProjectFile.deleted_at.is_(None),
                or_(
                    ProjectFile.original_filename.ilike(pattern),
                    ProjectFile.normalized_filename.ilike(pattern),
                    ProjectFile.extracted_text.ilike(pattern),
                ),
            )
            .order_by(ProjectFile.updated_at.desc())
            .limit(per_type)
        ).scalars()
    )
    items.extend(
        {
            "id": f.id,
            "resource_type": "file",
            "title": f.original_filename,
            "snippet": f.file_kind,
            "updated_at": f.updated_at,
            "project_id": f.project_id,
            "report_id": None,
        }
        for f in project_files
    )

    items.sort(key=lambda item: (item["updated_at"], str(item["id"])), reverse=True)
    record_provider_usage(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        source_id=None,
        usage=ProviderUsage(
            capability="source_discovery",
            operation="workspace_search",
            provider="database",
            model=None,
            metric="search_requests",
            units=1,
            metadata={"query_length": len(q), "result_count": len(items)},
        ),
        idempotency_key=f"workspace-search:{uuid.uuid4()}",
    )
    db.commit()
    return items[:limit], len(items)
