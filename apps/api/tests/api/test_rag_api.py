import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal, get_db
from app.main import app
from app.services import projects as projects_service


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
            delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            )
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
            id=uid,
            email=f"rag-api-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


@pytest.fixture()
def client(cleanup_users):
    uid = _mk_user(cleanup_users)

    def _override_user():
        with SessionLocal() as db:
            u = db.get(User, uid)
            assert u is not None
            return u

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()


def _mk_project(uid):
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        return p.id


def test_readiness_reports_missing_sources(client):
    c, uid = client
    pid = _mk_project(uid)
    resp = c.get(f"/api/v1/projects/{pid}/rag/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["saved_sources"] == 0
    assert body["processed_sources"] == 0
    assert body["semantic_ready_sources"] == 0


def test_memory_endpoint_empty(client):
    c, uid = client
    pid = _mk_project(uid)
    resp = c.get(f"/api/v1/projects/{pid}/rag/memory")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


def test_ownership_isolation(client):
    c, uid = client
    other_uid = _mk_user([])
    with SessionLocal() as db:
        other_p = projects_service.create_project(
            db, user_id=other_uid, name="other"
        )
        other_pid = other_p.id
    try:
        resp = c.post(
            f"/api/v1/projects/{other_pid}/rag/retrieve",
            json={"query": "x", "mode": "lexical", "async": False},
        )
        assert resp.status_code == 404
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(ProjectEvent).where(
                    ProjectEvent.project_id == other_pid
                )
            )
            db.execute(delete(Project).where(Project.id == other_pid))
            # M37: purge owned workspaces before deleting user
            db.execute(
                delete(Workspace).where(
                    Workspace.owner_user_id == other_uid
                )
            )
            db.execute(delete(User).where(User.id == other_uid))
            db.commit()
