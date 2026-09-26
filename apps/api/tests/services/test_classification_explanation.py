"""M22 — Classification explanation tests."""
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
                email=f"expl-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _latest_run(pid: uuid.UUID) -> ClassificationRun:
    with SessionLocal() as db:
        return db.execute(
            select(ClassificationRun)
            .where(
                ClassificationRun.project_id == pid,
                ClassificationRun.status.in_(
                    ("completed", "needs_review")
                ),
            )
            .order_by(
                ClassificationRun.created_at.desc(),
                ClassificationRun.id.desc(),
            )
            .limit(1)
        ).scalar_one()


def test_explanation_contains_selected_codes(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    run = _latest_run(pid)
    expl = run.explanation
    assert expl is not None
    assert "domain" in expl
    assert "paper_type" in expl
    assert "research_design" in expl
    assert "warnings" in expl

    assert expl["domain"]["selected"] == "computer_science"
    assert expl["domain"]["evidence_count"] >= 1


def test_explanation_evidence_mapped_correctly(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db,
            user_id=uid,
            name="Machine learning for medicine",
            domain="computer_science",
        )
        pid = p.id

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    run = _latest_run(pid)
    expl = run.explanation
    assert expl is not None

    domain_block = expl["domain"]
    for ev in domain_block["evidence"]:
        assert "signal_type" in ev
        assert "source_location" in ev
        assert "matched_text" in ev
        assert "weight" in ev
        assert 0.0 <= ev["weight"] <= 1.0
        assert ev["target_code"] == domain_block["selected"]


def test_explanation_warnings_for_unknown_dimensions(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="X", domain=None
        )
        pid = p.id

    with SessionLocal() as db:
        orchestrator.classify_project(db, project_id=pid, user_id=uid)

    run = _latest_run(pid)
    expl = run.explanation
    assert expl is not None

    warning_codes = {w["code"] for w in expl["warnings"]}
    assert "paper_type_unknown" in warning_codes
    assert "research_design_unknown" in warning_codes
