"""M24 — Research plan generate worker handler."""
from __future__ import annotations

import logging
import uuid

from app.db.models.project import Project
from app.db.session import SessionLocal
from app.services.research_planning import planner

logger = logging.getLogger(__name__)


def _parse_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def handle_research_plan_generate(ctx) -> dict:
    payload = ctx.payload or {}
    project_id_raw = payload.get("project_id")
    if not project_id_raw:
        raise ValueError("research_plan payload missing project_id")
    project_id = _parse_uuid(project_id_raw)
    if project_id is None:
        raise ValueError("research_plan project_id invalid")

    user_id = _parse_uuid(payload.get("user_id"))
    force = bool(payload.get("force", False))

    with SessionLocal() as db:
        if user_id is None:
            project = db.get(Project, project_id)
            if project is None:
                raise ValueError("research_plan project not found")
            user_id = project.user_id

        result = planner.generate_research_plan(
            db,
            user_id=user_id,
            project_id=project_id,
            force=force,
            commit=True,
        )
        return {
            "status": result.run.status,
            "skipped": result.skipped,
            "planning_mode": result.planning_mode,
            "plan_id": str(result.plan.id) if result.plan else None,
        }


__all__ = ["handle_research_plan_generate"]
