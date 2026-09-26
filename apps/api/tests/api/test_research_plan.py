"""M24 — API tests."""
from __future__ import annotations

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
            id=uid, email=f"rp-api-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


@pytest.fixture()
def client(cleanup_users) -> Iterator[tuple[TestClient, uuid.UUID]]:
    uid = _mk_user(cleanup_users)

    def _override_user() -> User:
        with SessionLocal() as db:
            u = db.get(User, uid)
            assert u is not None
            return u

    def _override_db() -> Iterator:
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


def _mk_project(uid) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        return p.id


def test_generate_sync(client):
    c, uid = client
    pid = _mk_project(uid)
    resp = c.post(
        f"/api/v1/projects/{pid}/research-plan/generate",
        json={"async": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("completed", "skipped")
    assert body["plan"] is not None
    assert body["plan"]["version"] >= 1


def test_generate_async_returns_queued(client):
    c, uid = client
    pid = _mk_project(uid)
    resp = c.post(
        f"/api/v1/projects/{pid}/research-plan/generate",
        json={"async": True},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["job_id"] is not None
    assert body["plan"] is None


def test_get_current_plan(client):
    c, uid = client
    pid = _mk_project(uid)
    c.post(
        f"/api/v1/projects/{pid}/research-plan/generate",
        json={"async": False},
    )
    resp = c.get(f"/api/v1/projects/{pid}/research-plan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"


def test_get_versions(client):
    c, uid = client
    pid = _mk_project(uid)
    c.post(
        f"/api/v1/projects/{pid}/research-plan/generate",
        json={"async": False},
    )
    resp = c.get(f"/api/v1/projects/{pid}/research-plan/versions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1


def test_get_coverage(client):
    c, uid = client
    pid = _mk_project(uid)
    c.post(
        f"/api/v1/projects/{pid}/research-plan/generate",
        json={"async": False},
    )
    resp = c.get(f"/api/v1/projects/{pid}/research-plan/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert "coverage_score" in body
    assert "coverage_state" in body


def test_validate_endpoint(client):
    c, uid = client
    pid = _mk_project(uid)
    c.post(
        f"/api/v1/projects/{pid}/research-plan/generate",
        json={"async": False},
    )
    resp = c.post(f"/api/v1/projects/{pid}/research-plan/validate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["validation_status"] in ("valid", "invalid")
