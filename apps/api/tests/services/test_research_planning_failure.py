"""M24 — Failure recovery tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_plan import ResearchPlan, ResearchPlanRun
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
            id=uid, email=f"rp-fail-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def test_failure_writes_failed_run(cleanup_users, monkeypatch):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id

    from app.services.research_planning import templates as tpl_svc

    def _boom(*a, **k):
        raise RuntimeError("simulated planner crash")

    monkeypatch.setattr(tpl_svc, "select_template", _boom)

    with SessionLocal() as db, pytest.raises(RuntimeError):
        planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )

    with SessionLocal() as db:
        failed_runs = db.execute(
            select(func.count()).select_from(ResearchPlanRun).where(
                ResearchPlanRun.project_id == pid,
                ResearchPlanRun.status == "failed",
            )
        ).scalar_one()
        ready_plans = db.execute(
            select(func.count()).select_from(ResearchPlan).where(
                ResearchPlan.project_id == pid,
                ResearchPlan.status == "ready",
            )
        ).scalar_one()
        failed_events = db.execute(
            select(func.count()).select_from(ProjectEvent).where(
                ProjectEvent.project_id == pid,
                ProjectEvent.event_type
                == "research_plan_generation_failed",
            )
        ).scalar_one()
    assert failed_runs == 1
    assert ready_plans == 0
    assert failed_events == 1


def test_previous_ready_plan_survives_failure(
    cleanup_users, monkeypatch
):
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
    plan_id = r1.plan.id

    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.research_questions = ["X?"]
        db.commit()

    from app.services.research_planning import templates as tpl_svc

    def _boom(*a, **k):
        raise RuntimeError("simulated planner crash")

    monkeypatch.setattr(tpl_svc, "select_template", _boom)

    with SessionLocal() as db, pytest.raises(RuntimeError):
        planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )

    with SessionLocal() as db:
        v1 = db.get(ResearchPlan, plan_id)
    assert v1 is not None
    assert v1.status == "ready"
