"""M25 — Query layer tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.exceptions import KnowledgeGraphNotFound
from app.db.models.knowledge_graph import KnowledgeGraphNode
from app.db.models.project import Project, ProjectEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.knowledge_graph import builder, queries


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
            id=uid, email=f"kg-q-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def test_get_graph_raises_when_no_graph(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id
    with SessionLocal() as db, pytest.raises(KnowledgeGraphNotFound):
        queries.get_graph(db, project_id=pid)


def test_get_graph_summary(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id
    with SessionLocal() as db:
        builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    with SessionLocal() as db:
        summary = queries.get_graph_summary(db, project_id=pid)
    assert summary["status"] == "ready"
    assert summary["node_count"] >= 1
    assert "project" in summary["node_type_counts"]


def test_get_neighbors_bounded(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id
    with SessionLocal() as db:
        builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    with SessionLocal() as db:
        node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.project_id == pid,
                KnowledgeGraphNode.node_type == "project",
            )
        ).scalar_one()
        neighbors = queries.get_neighbors(
            db, project_id=pid, node_id=node.id, limit=10,
        )
    assert isinstance(neighbors, list)
