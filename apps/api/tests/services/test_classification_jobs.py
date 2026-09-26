"""M22 — Classification job idempotency tests.

Cover the *classification-level* idempotency guarantees that back
the job worker:

  * running the same context twice does not duplicate work;
  * a different context does;
  * a failed attempt does not poison the next retry.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_classification import (
    ClassificationEvidence,
    ClassificationRun,
    ProjectClassification,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.classification import orchestrator


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
            delete(ClassificationEvidence).where(
                ClassificationEvidence.classification_id.in_(
                    select(ProjectClassification.id).where(
                        ProjectClassification.project_id.in_(pids)
                    )
                )
            )
        )
        db.execute(
            delete(ClassificationRun).where(
                ClassificationRun.project_id.in_(pids)
            )
        )
        db.execute(
            delete(ProjectClassification).where(
                ProjectClassification.project_id.in_(pids)
            )
        )
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
        db.add(
            User(
                id=uid,
                email=f"jobs-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def test_duplicate_job_does_not_execute_twice(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    with SessionLocal() as db:
        runs = list(
            db.execute(
                select(ClassificationRun).where(
                    ClassificationRun.project_id == pid
                )
            )
            .scalars()
            .all()
        )
    completed_like = [
        r for r in runs if r.status in ("completed", "needs_review")
    ]
    assert len(completed_like) == 1
    skipped = [r for r in runs if r.status == "skipped"]
    assert len(skipped) == 1


def test_completed_hash_skips_execution(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    with SessionLocal() as db:
        runs_before = db.execute(
            select(ClassificationRun).where(
                ClassificationRun.project_id == pid,
                ClassificationRun.status.in_(
                    ("completed", "needs_review")
                ),
            )
        ).scalars().all()
        assert len(runs_before) == 1
        completed_hash = runs_before[0].context_hash

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    with SessionLocal() as db:
        runs_after = db.execute(
            select(ClassificationRun).where(
                ClassificationRun.project_id == pid,
                ClassificationRun.status.in_(
                    ("completed", "needs_review")
                ),
            )
        ).scalars().all()
        assert len(runs_after) == 1
        assert runs_after[0].context_hash == completed_hash


def test_retry_after_failure_succeeds(cleanup_users, monkeypatch):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    def _boom(*a, **k):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(orchestrator, "classify_domain", _boom)

    with SessionLocal() as db, pytest.raises(RuntimeError):
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    monkeypatch.undo()

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    with SessionLocal() as db:
        runs = list(
            db.execute(
                select(ClassificationRun)
                .where(ClassificationRun.project_id == pid)
                .order_by(ClassificationRun.created_at.asc())
            )
            .scalars()
            .all()
        )
    assert len(runs) == 2
    assert runs[0].status == "failed"
    assert runs[1].status in ("completed", "needs_review")


def test_failure_after_all_attempts_keeps_current_state_failed(
    cleanup_users, monkeypatch
):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    def _boom(*a, **k):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(orchestrator, "classify_domain", _boom)

    for _ in range(3):
        with SessionLocal() as db, pytest.raises(RuntimeError):
            orchestrator.classify_project(
                db, project_id=pid, user_id=uid
            )

    with SessionLocal() as db:
        row = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == pid
            )
        ).scalar_one()
    assert row.status == "failed"
    assert row.error_message is not None

    with SessionLocal() as db:
        runs = list(
            db.execute(
                select(ClassificationRun).where(
                    ClassificationRun.project_id == pid
                )
            )
            .scalars()
            .all()
        )
    assert len(runs) == 3
    assert all(r.status == "failed" for r in runs)
