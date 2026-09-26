"""M21 — Failure-state tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.exceptions import ClassificationInvalidPayload
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_classification import ProjectClassification
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
                id=uid, email=f"f-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def test_first_time_failure_creates_failed_row(
    cleanup_users, monkeypatch
):
    uid = _mk_user(cleanup_users)

    def _boom(*a, **k):
        raise RuntimeError("simulated classifier crash")

    monkeypatch.setattr(orchestrator, "classify_domain", _boom)

    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        with pytest.raises(RuntimeError):
            orchestrator.classify_project(
                db, project_id=p.id, user_id=uid
            )

        row = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == p.id
            )
        ).scalar_one()
        assert row.status == "failed"
        assert row.error_message is not None

        events = db.execute(
            select(ProjectEvent).where(
                ProjectEvent.project_id == p.id,
                ProjectEvent.event_type == "classification_failed",
            )
        ).scalars().all()
        assert len(events) == 1


def test_failure_in_context_build_creates_failed_row(
    cleanup_users, monkeypatch
):
    uid = _mk_user(cleanup_users)

    def _boom(*a, **k):
        raise RuntimeError("context build crash")

    monkeypatch.setattr(orchestrator, "build_context", _boom)

    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        with pytest.raises(RuntimeError):
            orchestrator.classify_project(
                db, project_id=p.id, user_id=uid
            )

        row = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == p.id
            )
        ).scalar_one()
        assert row.status == "failed"


def test_classification_use_llm_flag_rejected(
    cleanup_users, monkeypatch
):
    uid = _mk_user(cleanup_users)
    s = get_settings()
    monkeypatch.setattr(s, "classification_use_llm", True)

    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        with pytest.raises(ClassificationInvalidPayload):
            orchestrator.classify_project(
                db, project_id=p.id, user_id=uid
            )
