"""M18-A — Project API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services.rate_limit import set_login_rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_rate_limiter() -> Iterator[None]:
    set_login_rate_limiter(None)
    yield
    set_login_rate_limiter(None)


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        project_ids = select(Project.id).where(Project.user_id.in_(user_ids))
        db.execute(
            delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(project_ids)
            )
        )
        db.execute(delete(Report).where(Report.user_id.in_(user_ids)))
        db.execute(delete(Project).where(Project.user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register_and_login(cleanup_users):
    email = f"proj-{uuid.uuid4().hex}@example.com"
    password = "Correct Horse Battery Staple!"
    r = client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert r.status_code == 201, r.text
    user_id = uuid.UUID(r.json()["id"])
    cleanup_users.append(user_id)
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return user_id, r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_project(token: str, name: str = "Alpha", **kw) -> dict:
    r = client.post(
        "/api/v1/projects", headers=_auth(token), json={"name": name, **kw}
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- CRUD ----------------------------------------------------------------
def test_create_project(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    body = _create_project(token, "Alpha", domain="physics")
    assert body["name"] == "Alpha"
    assert body["status"] == "draft"
    assert body["report_count"] == 0


def test_get_project(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    created = _create_project(token, "Alpha")
    r = client.get(f"/api/v1/projects/{created['id']}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_list_projects(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    for n in ("A", "B", "C"):
        _create_project(token, n)
    r = client.get("/api/v1/projects", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_update_project(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "Old")["id"]
    r = client.patch(
        f"/api/v1/projects/{pid}",
        headers=_auth(token),
        json={"name": "New", "research_questions": ["Q1", "Q2"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "New"
    assert body["research_questions"] == ["Q1", "Q2"]


def test_patch_omitted_does_not_touch(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "A", description="hello")["id"]
    r = client.patch(f"/api/v1/projects/{pid}", headers=_auth(token), json={})
    assert r.status_code == 200
    assert r.json()["description"] == "hello"


def test_patch_null_clears_field(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "A", description="hello")["id"]
    r = client.patch(
        f"/api/v1/projects/{pid}",
        headers=_auth(token),
        json={"description": None},
    )
    assert r.status_code == 200
    assert r.json()["description"] is None


def test_patch_rejects_null_name(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "A")["id"]
    r = client.patch(
        f"/api/v1/projects/{pid}",
        headers=_auth(token),
        json={"name": None},
    )
    assert r.status_code == 422


def test_archive_project(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "A")["id"]
    r = client.post(f"/api/v1/projects/{pid}/archive", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "archived"


def test_archive_idempotent(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "A")["id"]
    first = client.post(
        f"/api/v1/projects/{pid}/archive", headers=_auth(token)
    )
    second = client.post(
        f"/api/v1/projects/{pid}/archive", headers=_auth(token)
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "archived"


# --- Cross-user ---------------------------------------------------------
def test_cross_user_get_404(cleanup_users):
    _, ta = _register_and_login(cleanup_users)
    _, tb = _register_and_login(cleanup_users)
    pid = _create_project(ta, "A")["id"]
    r = client.get(f"/api/v1/projects/{pid}", headers=_auth(tb))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_cross_user_update_404(cleanup_users):
    _, ta = _register_and_login(cleanup_users)
    _, tb = _register_and_login(cleanup_users)
    pid = _create_project(ta, "A")["id"]
    r = client.patch(
        f"/api/v1/projects/{pid}",
        headers=_auth(tb),
        json={"name": "hacked"},
    )
    assert r.status_code == 404


def test_cross_user_archive_404(cleanup_users):
    _, ta = _register_and_login(cleanup_users)
    _, tb = _register_and_login(cleanup_users)
    pid = _create_project(ta, "A")["id"]
    r = client.post(f"/api/v1/projects/{pid}/archive", headers=_auth(tb))
    assert r.status_code == 404


def test_cross_user_list_reports_404(cleanup_users):
    _, ta = _register_and_login(cleanup_users)
    _, tb = _register_and_login(cleanup_users)
    pid = _create_project(ta, "A")["id"]
    r = client.get(f"/api/v1/projects/{pid}/reports", headers=_auth(tb))
    assert r.status_code == 404


# --- Report → project attach --------------------------------------------
def _create_report(
    token: str, topic: str = "T", project_id: str | None = None
):
    body: dict = {"topic": topic, "output_language": "en"}
    if project_id is not None:
        body["project_id"] = project_id
    return client.post("/api/v1/reports", headers=_auth(token), json=body)


def test_create_report_without_project(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    r = _create_report(token, "orphan")
    assert r.status_code == 201
    assert r.json()["project_id"] is None


def test_create_report_with_project(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "A")["id"]
    r = _create_report(token, "attached", project_id=pid)
    assert r.status_code == 201
    assert r.json()["project_id"] == pid


def test_create_report_with_foreign_project_404(cleanup_users):
    _, ta = _register_and_login(cleanup_users)
    _, tb = _register_and_login(cleanup_users)
    pid = _create_project(ta, "A")["id"]
    r = _create_report(tb, "evil", project_id=pid)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_create_report_with_archived_project_409(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "A")["id"]
    client.post(f"/api/v1/projects/{pid}/archive", headers=_auth(token))
    r = _create_report(token, "late", project_id=pid)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PROJECT_REPORT_ATTACH_FORBIDDEN"


def test_list_reports_by_project(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "A")["id"]
    _create_report(token, "in-1", project_id=pid)
    _create_report(token, "in-2", project_id=pid)
    _create_report(token, "out")
    r = client.get(f"/api/v1/projects/{pid}/reports", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert {it["topic"] for it in data["items"]} == {"in-1", "in-2"}


def test_project_report_count_reflects_attachments(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _create_project(token, "A")["id"]
    _create_report(token, "r1", project_id=pid)
    _create_report(token, "r2", project_id=pid)
    r = client.get(f"/api/v1/projects/{pid}", headers=_auth(token))
    assert r.json()["report_count"] == 2
