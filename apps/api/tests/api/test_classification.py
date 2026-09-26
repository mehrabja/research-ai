"""M21 — Classification API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.report import Report
from app.db.models.research_classification import ProjectClassification
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.main import app
from app.services.rate_limit import set_login_rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("FILE_STORAGE_LOCAL_ROOT", str(tmp_path))
    get_settings.cache_clear()
    set_login_rate_limiter(None)
    yield
    set_login_rate_limiter(None)
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
            delete(ProjectClassification).where(
                ProjectClassification.project_id.in_(pids)
            )
        )
        db.execute(
            delete(ProjectFileEvent).where(
                ProjectFileEvent.project_file_id.in_(
                    select(ProjectFile.id).where(
                        ProjectFile.project_id.in_(pids)
                    )
                )
            )
        )
        db.execute(
            delete(ProjectFile).where(ProjectFile.project_id.in_(pids))
        )
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Report).where(Report.user_id.in_(uids)))
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(uids)
            )
        )
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _reg(cleanup_users):
    email = f"c-{uuid.uuid4().hex}@e.com"
    pw = "Correct Horse Battery Staple!"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pw},
    )
    assert r.status_code == 201
    uid = uuid.UUID(r.json()["id"])
    cleanup_users.append(uid)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": pw},
    )
    return uid, r.json()["access_token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _mk_project(token, *, domain=None) -> str:
    body = {"name": "P"}
    if domain:
        body["domain"] = domain
    return client.post(
        "/api/v1/projects", headers=_auth(token), json=body
    ).json()["id"]


def test_get_creates_row(cleanup_users):
    _, token = _reg(cleanup_users)
    pid = _mk_project(token, domain="computer_science")
    r = client.get(
        f"/api/v1/projects/{pid}/classification", headers=_auth(token)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["domain"]["source"] == "explicit"
    assert body["status"] in ("completed", "needs_review")


def test_recompute_endpoint(cleanup_users):
    _, token = _reg(cleanup_users)
    pid = _mk_project(token)
    r = client.post(
        f"/api/v1/projects/{pid}/classification/recompute",
        headers=_auth(token),
    )
    assert r.status_code == 200


def test_override_endpoint(cleanup_users):
    _, token = _reg(cleanup_users)
    pid = _mk_project(token)
    r = client.patch(
        f"/api/v1/projects/{pid}/classification",
        headers=_auth(token),
        json={
            "domain_code": "medicine",
            "paper_type_code": "cohort_study",
            "research_design_code": "cohort",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["domain"]["source"] == "user_override"


def test_override_invalid_code(cleanup_users):
    _, token = _reg(cleanup_users)
    pid = _mk_project(token)
    r = client.patch(
        f"/api/v1/projects/{pid}/classification",
        headers=_auth(token),
        json={"domain_code": "nope_not_real"},
    )
    assert r.status_code == 404


def test_ownership_get_404(cleanup_users):
    _, ta = _reg(cleanup_users)
    _, tb = _reg(cleanup_users)
    pid = _mk_project(ta)
    r = client.get(
        f"/api/v1/projects/{pid}/classification", headers=_auth(tb)
    )
    assert r.status_code == 404


def test_evidence_list(cleanup_users):
    _, token = _reg(cleanup_users)
    pid = _mk_project(token, domain="computer_science")
    client.post(
        f"/api/v1/projects/{pid}/classification/recompute",
        headers=_auth(token),
    )
    r = client.get(
        f"/api/v1/projects/{pid}/classification/evidence",
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert data["items"][0]["signal_type"] == "explicit_field"


def test_recompute_after_upload_invalidates(cleanup_users):
    _, token = _reg(cleanup_users)
    pid = _mk_project(token, domain="computer_science")

    r = client.get(
        f"/api/v1/projects/{pid}/classification", headers=_auth(token)
    )
    assert r.status_code == 200
    body1 = r.json()
    chunks1 = (
        body1["context_meta"] and
        body1["context_meta"].get("chunks_used")
    )

    client.post(
        f"/api/v1/projects/{pid}/files",
        headers=_auth(token),
        files={"file": ("a.txt", b"hello", "text/plain")},
    )

    r2 = client.post(
        f"/api/v1/projects/{pid}/classification/recompute",
        headers=_auth(token),
    )
    assert r2.status_code == 200
    body2 = r2.json()
    chunks2 = (
        body2["context_meta"] and
        body2["context_meta"].get("chunks_used")
    )
    assert (chunks2 or 0) > (chunks1 or 0)
