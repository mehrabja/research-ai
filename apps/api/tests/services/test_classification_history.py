"""M22 — Classification history tests."""
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
                email=f"hist-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _runs_for(pid: uuid.UUID) -> list[ClassificationRun]:
    with SessionLocal() as db:
        return list(
            db.execute(
                select(ClassificationRun)
                .where(ClassificationRun.project_id == pid)
                .order_by(ClassificationRun.created_at.asc())
            )
            .scalars()
            .all()
        )


def test_successful_run_creates_history_row(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    runs = _runs_for(pid)
    assert len(runs) == 1
    r = runs[0]
    assert r.status in ("completed", "needs_review")
    assert r.context_hash is not None
    assert r.explanation is not None
    assert r.duration_ms is not None and r.duration_ms >= 0


def test_failed_run_creates_failed_history(
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

    with SessionLocal() as db, pytest.raises(RuntimeError):
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    runs = _runs_for(pid)
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].error_message is not None
    assert "simulated crash" in runs[0].error_message


def test_two_different_hashes_create_two_runs(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    # Change context → different hash.
    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.description = "A study of machine learning methods"
        db.commit()

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    runs = _runs_for(pid)
    completed_like = [
        r for r in runs if r.status in ("completed", "needs_review")
    ]
    assert len(completed_like) == 2
    hashes = {r.context_hash for r in completed_like}
    assert len(hashes) == 2


def test_same_hash_skip_creates_no_duplicate_work(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    # Same context → must skip, not re-classify.
    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    runs = _runs_for(pid)
    completed_like = [
        r for r in runs if r.status in ("completed", "needs_review")
    ]
    skipped = [r for r in runs if r.status == "skipped"]
    assert len(completed_like) == 1
    assert len(skipped) == 1
