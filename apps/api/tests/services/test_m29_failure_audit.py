"""M29 — durable failed-run audit."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.technical_intelligence import (
    TechnicalIntelligenceRun,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.technical_intelligence import engine as e_svc
from app.services.technical_intelligence import persistence as p_svc


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = [r[0] for r in db.execute(
            select(Project.id).where(Project.user_id.in_(uids))
        ).all()]
        if pids:
            db.execute(delete(TechnicalIntelligenceRun).where(
                TechnicalIntelligenceRun.project_id.in_(pids)
            ))
            db.execute(delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            ))
            db.execute(delete(Project).where(Project.id.in_(pids)))
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
            id=uid,
            email=f"m29f-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _mk_project(uid) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science",
        )
        return p.id


def test_failed_run_persisted(
    cleanup_users, monkeypatch
) -> None:
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(e_svc, "run_technical_intelligence", _boom)

    with SessionLocal() as db, pytest.raises(RuntimeError, match="boom"):
        p_svc.run_m29_persisted(db, project_id=pid, commit=True)

    with SessionLocal() as db:
        rows = list(db.execute(
            select(TechnicalIntelligenceRun).where(
                TechnicalIntelligenceRun.project_id == pid,
                TechnicalIntelligenceRun.status == "failed",
            )
        ).scalars().all())
    assert len(rows) == 1
    assert "boom" in (rows[0].error_message or "")
