"""M23 — Literature API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.literature import (
    LiteratureCluster,
    LiteratureGap,
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.source import Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)


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
            delete(LiteratureIntelligenceRun).where(
                LiteratureIntelligenceRun.project_id.in_(pids)
            )
        )
        db.execute(
            delete(LiteratureGap).where(
                LiteratureGap.project_id.in_(pids)
            )
        )
        db.execute(
            delete(LiteratureCluster).where(
                LiteratureCluster.project_id.in_(pids)
            )
        )
        db.execute(
            delete(ProjectLiteratureItem).where(
                ProjectLiteratureItem.project_id.in_(pids)
            )
        )
        rids = select(Report.id).where(Report.project_id.in_(pids))
        db.execute(delete(Source).where(Source.report_id.in_(rids)))
        db.execute(delete(Report).where(Report.project_id.in_(pids)))
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _reg(uids) -> tuple[str, str]:
    email = f"lit-api-{uuid.uuid4().hex[:8]}@e.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password1234567890!"},
    )
    assert r.status_code in (200, 201), r.text
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password1234567890!"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    with SessionLocal() as db:
        u = db.execute(
            select(User).where(User.email == email)
        ).scalar_one()
    uids.append(u.id)
    return email, token


def _mk_project(token: str) -> str:
    r = client.post(
        "/api/v1/projects",
        headers=_auth(token),
        json={"name": "P", "domain": "computer_science"},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _add_source(project_id: str, title: str, uid: uuid.UUID) -> None:
    with SessionLocal() as db:
        r = Report(
            user_id=uid,
            project_id=uuid.UUID(project_id),
            topic="R",
            output_language="en",
            status="draft",
        )
        db.add(r)
        db.flush()
        db.add(
            Source(
                report_id=r.id, title=title, status="metadata_only"
            )
        )
        db.commit()


def test_literature_endpoints_require_ownership(cleanup_users):
    _, token = _reg(cleanup_users)
    r = client.get(
        f"/api/v1/projects/{uuid.uuid4()}/literature",
        headers=_auth(token),
    )
    assert r.status_code in (403, 404)


def test_literature_list_and_analyze(cleanup_users):
    uid_email, token = _reg(cleanup_users)
    pid = _mk_project(token)
    with SessionLocal() as db:
        u = db.execute(
            select(User).where(User.email == uid_email)
        ).scalar_one()
        uid = u.id
    _add_source(pid, "Test paper", uid)

    r = client.post(
        f"/api/v1/projects/{pid}/literature/analyze",
        headers=_auth(token),
        json={"force": False},
    )
    assert r.status_code in (200, 202), r.text
    body = r.json()
    # Sync mode by default.
    if r.status_code == 200:
        assert body["status"] in ("completed", "skipped")
        assert body["run"] is not None
    else:
        assert body["status"] == "queued"
        assert body["job_id"] is not None
        assert body["run"] is None

    r = client.get(
        f"/api/v1/projects/{pid}/literature",
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert "items" in body


def test_screening_override(cleanup_users):
    email, token = _reg(cleanup_users)
    pid = _mk_project(token)
    with SessionLocal() as db:
        u = db.execute(
            select(User).where(User.email == email)
        ).scalar_one()
        uid = u.id
    _add_source(pid, "Test paper", uid)
    client.post(
        f"/api/v1/projects/{pid}/literature/analyze",
        headers=_auth(token),
        json={"force": False},
    )
    r = client.get(
        f"/api/v1/projects/{pid}/literature",
        headers=_auth(token),
    )
    assert r.status_code == 200
    item_id = r.json()["items"][0]["id"]

    r = client.patch(
        f"/api/v1/projects/{pid}/literature/{item_id}",
        headers=_auth(token),
        json={"screening_status": "included", "reason": "manual"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["screening_status"] == "included"
    assert r.json()["manual_override"] is True


def test_clusters_gaps_runs_endpoints(cleanup_users):
    _email, token = _reg(cleanup_users)
    pid = _mk_project(token)
    client.post(
        f"/api/v1/projects/{pid}/literature/analyze",
        headers=_auth(token),
        json={"force": False},
    )
    for path in ("clusters", "gaps", "runs"):
        r = client.get(
            f"/api/v1/projects/{pid}/literature/{path}",
            headers=_auth(token),
        )
        assert r.status_code == 200, (path, r.text)
