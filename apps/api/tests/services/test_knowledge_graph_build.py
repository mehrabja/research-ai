"""M25 — Graph build tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.db.models.knowledge_graph import (
    KnowledgeGraphBuildRun,
    KnowledgeGraphNode,
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
            id=uid, email=f"kg-b-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _mk_project(uid) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        return p.id


def test_graph_build_creates_nodes_and_edges(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        result = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    assert result.skipped is False
    assert result.run.status == "completed"
    assert result.graph_version is not None
    assert result.node_count >= 1

    with SessionLocal() as db:
        gv = db.get(KnowledgeGraphVersion, result.graph_version.id)
        assert gv is not None
        assert gv.status == "ready"
        assert gv.node_count == result.node_count
        nodes = list(db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.graph_version_id == gv.id
            )
        ).scalars().all())
    assert len(nodes) >= 1
    assert any(n.node_type == "project" for n in nodes)


def test_graph_build_is_idempotent(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        r1 = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    assert r1.skipped is False

    with SessionLocal() as db:
        r2 = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    assert r2.skipped is True
    assert r2.run.status == "skipped"

    with SessionLocal() as db:
        ready = db.execute(
            select(func.count()).select_from(KnowledgeGraphVersion).where(
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


def test_graph_build_supersedes_previous(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        r1 = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    v1 = r1.graph_version.id

    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.research_questions = ["a different question"]
        db.commit()

    with SessionLocal() as db:
        r2 = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    assert r2.skipped is False
    assert r2.graph_version.version == 2

    with SessionLocal() as db:
        v1_row = db.get(KnowledgeGraphVersion, v1)
        assert v1_row.status == "superseded"
        ready = db.execute(
            select(func.count()).select_from(KnowledgeGraphVersion).where(
                KnowledgeGraphVersion.project_id == pid,
                KnowledgeGraphVersion.status == "ready",
            )
        ).scalar_one()
    assert ready == 1


def test_graph_build_failure_is_recorded(cleanup_users, monkeypatch):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    from app.services.knowledge_graph import builder as b

    def _boom(*a, **k):
        raise RuntimeError("simulated graph crash")

    monkeypatch.setattr(b, "_collect_nodes_edges", _boom)

    with SessionLocal() as db, pytest.raises(RuntimeError):
        builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )

    with SessionLocal() as db:
        failed = db.execute(
            select(func.count()).select_from(
                KnowledgeGraphBuildRun
            ).where(
                KnowledgeGraphBuildRun.project_id == pid,
                KnowledgeGraphBuildRun.status == "failed",
            )
        ).scalar_one()
        failed_events = db.execute(
            select(func.count()).select_from(ProjectEvent).where(
                ProjectEvent.project_id == pid,
                ProjectEvent.event_type
                == "knowledge_graph_generation_failed",
            )
        ).scalar_one()
    assert failed == 1
    assert failed_events == 1
