"""M21 — Concurrency tests."""
from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_classification import (
    ClassificationEvidence,
    ProjectClassification,
)
from app.db.models.user import User
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
                id=uid, email=f"cc-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def test_concurrent_runs_produce_single_row(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    errors: list = []

    def _run():
        try:
            with SessionLocal() as db:
                orchestrator.classify_project(
                    db, project_id=pid, user_id=uid
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    with SessionLocal() as db:
        rows = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == pid
            )
        ).scalars().all()
        assert len(rows) == 1


def test_failure_does_not_clobber_concurrent_success(
    cleanup_users, monkeypatch
):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    # First successful classification. With only "P" as project name
    # and no paper/design signals, the classifier yields
    # ``needs_review`` (see test_classification_needs_review.py).
    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    with SessionLocal() as db:
        completed = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == pid
            )
        ).scalar_one()
        assert completed.status == "needs_review"
        completed_id = completed.id

    def _boom(*a, **k):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(orchestrator, "classify_domain", _boom)

    # Second classification attempt fails. Because the existing row
    # is not ``pending``, _write_failure() must leave it untouched.
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
        assert row.id == completed_id
        assert row.status == "needs_review"