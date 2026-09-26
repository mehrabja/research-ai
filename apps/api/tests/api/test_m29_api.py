"""M29 — API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.technical_intelligence import (
    TechnicalIntelligenceRun,
)
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
            email=f"m29api-{uid.hex[:8]}@e.com",
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
            db, user_id=uid, name="P", domain="computer_science",
        )
        return p.id


def test_requires_auth() -> None:
    c = TestClient(app)
    r = c.post(
        f"/api/v1/projects/{uuid.uuid4()}/technical-intelligence/"
        "generate",
        json={"async": False},
    )
    assert r.status_code in (401, 403)


def test_unknown_project_404(client) -> None:
    c, _uid = client
    r = c.get(
        f"/api/v1/projects/{uuid.uuid4()}/technical-intelligence"
    )
    assert r.status_code == 404


def test_generate_sync_empty_project(client) -> None:
    c, uid = client
    pid = _mk_project(uid)
    r = c.post(
        f"/api/v1/projects/{pid}/technical-intelligence/generate",
        json={"async": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["run_id"] is not None
    assert body["context_hash"]


def test_get_current_after_generate(client) -> None:
    c, uid = client
    pid = _mk_project(uid)
    c.post(
        f"/api/v1/projects/{pid}/technical-intelligence/generate",
        json={"async": False},
    )
    r = c.get(f"/api/v1/projects/{pid}/technical-intelligence")
    assert r.status_code == 200
    body = r.json()
    assert body["run"]["status"] == "completed"
    assert body["fact_count"] == 0
    assert body["result_count"] == 0
    assert body["metric_count"] == 0


def test_get_current_404_before_generate(client) -> None:
    c, uid = client
    pid = _mk_project(uid)
    r = c.get(f"/api/v1/projects/{pid}/technical-intelligence")
    assert r.status_code == 404


def test_runs_history(client) -> None:
    c, uid = client
    pid = _mk_project(uid)
    c.post(
        f"/api/v1/projects/{pid}/technical-intelligence/generate",
        json={"async": False},
    )
    r = c.get(
        f"/api/v1/projects/{pid}/technical-intelligence/runs"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1


def test_cross_user_404(cleanup_users) -> None:
    owner = _mk_user(cleanup_users)
    other = _mk_user(cleanup_users)
    pid = _mk_project(owner)

    def _override_other() -> User:
        with SessionLocal() as db:
            u = db.get(User, other)
            assert u is not None
            return u

    def _override_db() -> Iterator:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = _override_other
    app.dependency_overrides[get_db] = _override_db
    try:
        c = TestClient(app)
        r = c.get(
            f"/api/v1/projects/{pid}/technical-intelligence"
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
