"""M24 — Jobs enqueue tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.jobs import Job
from app.db.models.project import Project, ProjectEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.research_planning import jobs as rp_jobs


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
        db.execute(delete(Job).where(Job.user_id.in_(uids)))
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
            id=uid, email=f"rp-job-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def test_enqueue_creates_correct_job_type(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id

    with SessionLocal() as db:
        job_id = rp_jobs.enqueue_research_plan(
            db, project_id=pid, user_id=uid
        )
        db.commit()

    assert job_id is not None
    with SessionLocal() as db:
        job = db.get(Job, job_id)
    assert job is not None
    assert job.job_type == "research_plan_generate"


def test_duplicate_enqueue_deduped(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id

    with SessionLocal() as db:
        jid1 = rp_jobs.enqueue_research_plan(
            db, project_id=pid, user_id=uid
        )
        db.commit()
    with SessionLocal() as db:
        jid2 = rp_jobs.enqueue_research_plan(
            db, project_id=pid, user_id=uid
        )
        db.commit()

    assert jid1 == jid2
