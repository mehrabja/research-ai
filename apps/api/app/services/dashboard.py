"""Workspace dashboard aggregates."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.citation import Claim, CitationRun
from app.db.models.jobs import Job
from app.db.models.membership import WorkspaceMembership
from app.db.models.plan import Plan, PlanEntitlement
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report
from app.db.models.source import Source
from app.db.models.subscription import Subscription
from app.db.models.usage import UsageEvent


def _active_workspace_ids(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    return list(
        db.execute(
            select(WorkspaceMembership.workspace_id).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.status == "active",
            )
        ).scalars().all()
    )


def get_dashboard_stats(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
) -> dict[str, int | None]:
    workspace_ids = _active_workspace_ids(db, user_id=user_id)
    if workspace_id is not None:
        workspace_ids = [
            item for item in workspace_ids if item == workspace_id
        ]

    if not workspace_ids:
        return {
            "active_projects": 0,
            "saved_sources": 0,
            "evidence_items": 0,
            "active_jobs": 0,
            "storage_bytes": 0,
            "ai_generation_units": 0,
            "ai_generation_limit": None,
            "workspace_count": 0,
        }

    active_projects = int(
        db.execute(
            select(func.count(Project.id)).where(
                Project.workspace_id.in_(workspace_ids),
                Project.status != "archived",
            )
        ).scalar_one()
    )
    saved_sources = int(
        db.execute(
            select(func.count(Source.id))
            .join(Report, Report.id == Source.report_id)
            .join(Project, Project.id == Report.project_id)
            .where(Project.workspace_id.in_(workspace_ids))
        ).scalar_one()
    )
    evidence_items = int(
        db.execute(
            select(func.count(Claim.id))
            .join(CitationRun, CitationRun.id == Claim.citation_run_id)
            .join(Project, Project.id == Report.project_id)
            .join(Report, Report.id == CitationRun.report_id)
            .where(Project.workspace_id.in_(workspace_ids))
        ).scalar_one()
    )
    active_jobs = int(
        db.execute(
            select(func.count(Job.id)).where(
                Job.user_id == user_id,
                Job.status.in_(("queued", "processing", "retrying")),
            )
        ).scalar_one()
    )
    storage_bytes = int(
        db.execute(
            select(func.coalesce(func.sum(ProjectFile.size_bytes), 0))
            .join(Project, Project.id == ProjectFile.project_id)
            .where(
                Project.workspace_id.in_(workspace_ids),
                ProjectFile.deleted_at.is_(None),
            )
        ).scalar_one()
    )

    period_start = datetime.now(UTC) - timedelta(days=30)
    generation_units = int(
        db.execute(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.workspace_id.in_(workspace_ids),
                UsageEvent.metric == "ai_generation_units",
                UsageEvent.usage_class == "internal",
                UsageEvent.occurred_at >= period_start,
            )
        ).scalar_one()
    )

    entitlement = db.execute(
        select(PlanEntitlement.limit_value)
        .join(Plan, Plan.id == PlanEntitlement.plan_id)
        .join(Subscription, Subscription.plan_id == Plan.id)
        .where(
            Subscription.workspace_id.in_(workspace_ids),
            Subscription.status.in_(("trialing", "active", "past_due")),
            PlanEntitlement.feature == "ai_generation_units",
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    return {
        "active_projects": active_projects,
        "saved_sources": saved_sources,
        "evidence_items": evidence_items,
        "active_jobs": active_jobs,
        "storage_bytes": storage_bytes,
        "ai_generation_units": generation_units,
        "ai_generation_limit": (
            int(entitlement) if entitlement is not None else None
        ),
        "workspace_count": len(workspace_ids),
    }
