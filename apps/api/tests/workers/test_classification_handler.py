"""M21 — Classification worker handler tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from app.workers.classification_handlers import (
    handle_research_classification,
)
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_classification import ProjectClassification
from app.db.models.user import User
from app.db.session import SessionLocal
from app.domain.jobs import JobContext
from app.services import jobs as jobs_service
from app.services import projects as projects_service


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
            delete(ProjectClassification).where(
                ProjectClassification.project_id.in_(pids)
            )
        )
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid, email=f"y-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _ctx(job) -> JobContext:
    return JobContext(
        job_id=job.id,
        job_type=job.job_type,
        attempt_count=job.attempt_count,
        worker_id="w-test",
        payload=dict(job.payload or {}),
    )


def test_handler_success(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        job = jobs_service.enqueue_job(
            db,
            job_type="research_classification",
            payload={"project_id": str(p.id)},
            idempotency_key=f"r:{p.id}:{uuid.uuid4()}",
            user_id=uid,
        ).job
        handle_research_classification(_ctx(job))
        row = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == p.id
            )
        ).scalar_one()
        assert row.status in ("completed", "needs_review")


def test_handler_missing_project_noop(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        job = jobs_service.enqueue_job(
            db,
            job_type="research_classification",
            payload={"project_id": str(uuid.uuid4())},
            idempotency_key=f"r:missing:{uuid.uuid4()}",
            user_id=uid,
        ).job
        handle_research_classification(_ctx(job))


def test_handler_malformed_payload_raises(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        job = jobs_service.enqueue_job(
            db,
            job_type="research_classification",
            payload={},
            user_id=uid,
        ).job
        with pytest.raises(ValueError):
            handle_research_classification(_ctx(job))


def test_handler_archived_project_noop(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        projects_service.archive_project(db, user_id=uid, project_id=p.id)
        job = jobs_service.enqueue_job(
            db,
            job_type="research_classification",
            payload={"project_id": str(p.id)},
            idempotency_key=f"r:arch:{p.id}:{uuid.uuid4()}",
            user_id=uid,
        ).job
        handle_research_classification(_ctx(job))
        row = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == p.id
            )
        ).scalar_one_or_none()
        assert row is None


def test_handler_idempotent_rerun(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        j1 = jobs_service.enqueue_job(
            db, job_type="research_classification",
            payload={"project_id": str(p.id)},
            idempotency_key=f"r:{p.id}:{uuid.uuid4()}", user_id=uid,
        ).job
        handle_research_classification(_ctx(j1))
        j2 = jobs_service.enqueue_job(
            db, job_type="research_classification",
            payload={"project_id": str(p.id)},
            idempotency_key=f"r:{p.id}:{uuid.uuid4()}", user_id=uid,
        ).job
        handle_research_classification(_ctx(j2))
        rows = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == p.id
            )
        ).scalars().all()
        assert len(rows) == 1
