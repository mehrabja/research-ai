"""M24 — Superseding / versioning tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_plan import ResearchPlan
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.research_planning import planner


@pytest.fixture(autouse=True)
def _clear_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(uids)
            )
        )
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid, email=f"rp-sup-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def test_new_context_supersedes_old_plan(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    with SessionLocal() as db:
        r1 = planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )
    assert r1.plan is not None
    assert r1.plan.version == 1
    assert r1.plan.status == "ready"
    v1_id = r1.plan.id

    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.research_questions = ["A different question."]
        db.commit()

    with SessionLocal() as db:
        r2 = planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )
    assert r2.skipped is False
    assert r2.plan is not None
    assert r2.plan.version == 2
    assert r2.plan.status == "ready"
    assert r2.plan.supersedes_plan_id == v1_id

    with SessionLocal() as db:
        v1 = db.get(ResearchPlan, v1_id)
        assert v1.status == "superseded"
        ready_count = db.execute(
            select(func.count()).select_from(ResearchPlan).where(
                ResearchPlan.project_id == pid,
                ResearchPlan.status == "ready",
            )
        ).scalar_one()
    assert ready_count == 1
