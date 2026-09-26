"""M24 — Idempotency tests for research planning."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_plan import (
    ResearchPlan,
    ResearchPlanRun,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.research_planning import context as ctx_svc
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
            id=uid, email=f"rp-id-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _mk_project(uid) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        return p.id


def test_same_context_skips_second(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        r1 = planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )
    assert r1.skipped is False
    assert r1.run.status == "completed"

    with SessionLocal() as db:
        r2 = planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )
    assert r2.skipped is True
    assert r2.run.status == "skipped"

    with SessionLocal() as db:
        ready = db.execute(
            select(func.count()).select_from(ResearchPlan).where(
                ResearchPlan.project_id == pid,
                ResearchPlan.status == "ready",
            )
        ).scalar_one()
        completed = db.execute(
            select(func.count()).select_from(ResearchPlanRun).where(
                ResearchPlanRun.project_id == pid,
                ResearchPlanRun.status == "completed",
            )
        ).scalar_one()
    assert ready == 1
    assert completed == 1


def test_force_does_not_duplicate(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )

    with SessionLocal() as db:
        r2 = planner.generate_research_plan(
            db, user_id=uid, project_id=pid, force=True
        )
    assert r2.skipped is True
    assert r2.run.status == "skipped"

    with SessionLocal() as db:
        completed = db.execute(
            select(func.count()).select_from(ResearchPlanRun).where(
                ResearchPlanRun.project_id == pid,
                ResearchPlanRun.status == "completed",
            )
        ).scalar_one()
    assert completed == 1


def test_research_question_change_invalidates_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        h1 = ctx_svc.compute_research_planning_hash(
            db, project_id=pid
        )
    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.research_questions = ["What is X?"]
        db.commit()
    with SessionLocal() as db:
        h2 = ctx_svc.compute_research_planning_hash(
            db, project_id=pid
        )
    assert h1 != h2


def test_hypotheses_change_invalidates_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        h1 = ctx_svc.compute_research_planning_hash(
            db, project_id=pid
        )
    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.hypotheses = ["H1"]
        db.commit()
    with SessionLocal() as db:
        h2 = ctx_svc.compute_research_planning_hash(
            db, project_id=pid
        )
    assert h1 != h2


def test_stable_when_no_input_changes(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h1 = ctx_svc.compute_research_planning_hash(
            db, project_id=pid
        )
    with SessionLocal() as db:
        h2 = ctx_svc.compute_research_planning_hash(
            db, project_id=pid
        )
    assert h1 == h2
