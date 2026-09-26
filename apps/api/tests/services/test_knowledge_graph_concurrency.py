"""M25 — Concurrency tests."""
from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.db.models.knowledge_graph import (
    KnowledgeGraphBuildRun,
    KnowledgeGraphVersion,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.knowledge_graph import builder


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
            id=uid, email=f"kg-cc-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def test_concurrent_builds_produce_one_active_graph(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id

    errors: list = []

    def _run():
        try:
            with SessionLocal() as db:
                builder.build_knowledge_graph(
                    db, user_id=uid, project_id=pid
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
        ready = db.execute(
            select(func.count()).select_from(
                KnowledgeGraphVersion
            ).where(
                KnowledgeGraphVersion.project_id == pid,
                KnowledgeGraphVersion.status == "ready",
            )
        ).scalar_one()
        completed = db.execute(
            select(func.count()).select_from(
                KnowledgeGraphBuildRun
            ).where(
                KnowledgeGraphBuildRun.project_id == pid,
                KnowledgeGraphBuildRun.status == "completed",
            )
        ).scalar_one()
    assert ready == 1
    assert completed == 1
