"""M21 — needs_review semantics tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
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
                id=uid, email=f"nr-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def test_empty_project_needs_review(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        # name is required and non-empty per Project domain rules.
        # "empty context" means no domain, no description, no files.
        p = projects_service.create_project(db, user_id=uid, name="X")
        row = orchestrator.classify_project(
            db, project_id=p.id, user_id=uid
        )
        # No signals → needs_review must be True.
        assert row.needs_review is True
        assert row.status == "needs_review"


def test_explicit_domain_still_needs_review_without_paper(
    cleanup_users,
):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        row = orchestrator.classify_project(
            db, project_id=p.id, user_id=uid
        )
        assert row.domain_source == "explicit"
        assert row.needs_review is True
