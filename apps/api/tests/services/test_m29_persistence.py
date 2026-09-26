"""M29 — idempotent persistence tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile
from app.db.models.technical_intelligence import (
    TechnicalIntelligenceRun,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.technical_intelligence import persistence as p_svc


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = [
            r[0]
            for r in db.execute(
                select(Project.id).where(Project.user_id.in_(uids))
            ).all()
        ]
        if pids:
            db.execute(delete(TechnicalIntelligenceRun).where(
                TechnicalIntelligenceRun.project_id.in_(pids)
            ))
            db.execute(delete(ProjectFile).where(
                ProjectFile.project_id.in_(pids)
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


def _mk_user(uids: list[uuid.UUID]) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid,
            email=f"m29p-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _mk_project(uid: uuid.UUID) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science",
        )
        return p.id


def test_persist_idempotent(cleanup_users) -> None:
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        r1 = p_svc.run_m29_persisted(db, project_id=pid, commit=True)
        status1 = r1.run.status
        hash1 = r1.run.context_hash
        skipped1 = r1.skipped
    assert status1 == "completed"
    assert skipped1 is False

    with SessionLocal() as db:
        r2 = p_svc.run_m29_persisted(db, project_id=pid, commit=True)
        status2 = r2.run.status
        hash2 = r2.run.context_hash
        skipped2 = r2.skipped
    assert status2 == "skipped"
    assert skipped2 is True
    assert hash2 == hash1


def test_force_does_not_duplicate(cleanup_users) -> None:
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        p_svc.run_m29_persisted(
            db, project_id=pid, force=True, commit=True,
        )

    with SessionLocal() as db:
        r2 = p_svc.run_m29_persisted(
            db, project_id=pid, force=True, commit=True,
        )
        skipped2 = r2.skipped
    assert skipped2 is True

    with SessionLocal() as db:
        completed = list(db.execute(
            select(TechnicalIntelligenceRun).where(
                TechnicalIntelligenceRun.project_id == pid,
                TechnicalIntelligenceRun.status == "completed",
            )
        ).scalars().all())
    assert len(completed) == 1
