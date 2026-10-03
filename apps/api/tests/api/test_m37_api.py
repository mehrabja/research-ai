"""M37 Phase 2-D — API surface tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.session import SessionLocal
from app.main import app
from tests._m37_cleanup import purge_test_users

client = TestClient(app)


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids)))
        db.execute(delete(Report).where(Report.user_id.in_(uids)))
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        purge_test_users(db, uids)
        db.commit()


def _reg(uids: list[uuid.UUID]) -> tuple[uuid.UUID, str]:
    email = f"api37-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Correct Horse Battery Staple!"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": pw})
    assert r.status_code == 201, r.text
    uid = uuid.UUID(r.json()["id"])
    uids.append(uid)
    r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    token = r.json()["access_token"]
    return uid, token


def _auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def test_create_workspace(cleanup_users):
    _uid, token = _reg(cleanup_users)
    r = client.post(
        "/api/v1/workspaces",
        headers=_auth(token),
        json={"name": "My Team"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "My Team"
    assert body["owner_user_id"]


def test_list_workspaces_includes_personal(cleanup_users):
    _uid, token = _reg(cleanup_users)
    client.post("/api/v1/workspaces", headers=_auth(token), json={"name": "A"})
    r = client.get("/api/v1/workspaces", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1


def test_cross_tenant_workspace_404(cleanup_users):
    _ua, ta = _reg(cleanup_users)
    _ub, tb = _reg(cleanup_users)
    r = client.post(
        "/api/v1/workspaces", headers=_auth(ta), json={"name": "a-only"}
    )
    wid = r.json()["id"]
    r2 = client.get(f"/api/v1/workspaces/{wid}", headers=_auth(tb))
    assert r2.status_code == 404


def test_invitation_roundtrip(cleanup_users):
    owner, to = _reg(cleanup_users)
    invitee_email = f"invitee-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/workspaces", headers=_auth(to), json={"name": "T"})
    wid = r.json()["id"]

    # upgrade to pro via direct DB so member quota allows accepting
    with SessionLocal() as db:
        from app.db.models.plan import Plan
        from app.db.models.subscription import Subscription
        pro = db.execute(select(Plan).where(Plan.code == "pro")).scalar_one()
        sub = db.execute(
            select(Subscription).where(Subscription.workspace_id == uuid.UUID(wid))
        ).scalar_one()
        sub.plan_id = pro.id
        db.commit()

    r = client.post(
        f"/api/v1/workspaces/{wid}/members/invitations",
        headers=_auth(to),
        json={"email": invitee_email, "role": "member"},
    )
    assert r.status_code == 201, r.text
    raw_token = r.json()["token"]
    assert "token_hash" not in r.text

    # register invitee
    pw = "Correct Horse Battery Staple!"
    r = client.post("/api/v1/auth/register", json={"email": invitee_email, "password": pw})
    assert r.status_code == 201
    iid = uuid.UUID(r.json()["id"])
    cleanup_users.append(iid)
    r = client.post("/api/v1/auth/login", json={"email": invitee_email, "password": pw})
    it = r.json()["access_token"]

    r = client.post(f"/api/v1/invitations/{raw_token}/accept", headers=_auth(it))
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "member"


def test_usage_endpoint(cleanup_users):
    _uid, token = _reg(cleanup_users)
    r = client.post("/api/v1/workspaces", headers=_auth(token), json={"name": "U"})
    wid = r.json()["id"]
    r = client.get(f"/api/v1/workspaces/{wid}/usage", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert "period_start" in body
    assert "period_end" in body
    assert isinstance(body["items"], list)


def test_usage_includes_active_file_storage(cleanup_users):
    _uid, token = _reg(cleanup_users)
    r = client.post("/api/v1/workspaces", headers=_auth(token), json={"name": "Storage"})
    wid = r.json()["id"]
    project = client.post(
        "/api/v1/projects",
        headers=_auth(token),
        json={"workspace_id": wid, "name": "P"},
    )
    assert project.status_code == 201, project.text
    pid = project.json()["id"]
    upload = client.post(
        f"/api/v1/projects/{pid}/files",
        headers=_auth(token),
        files={"file": ("paper.txt", b"12345", "text/plain")},
    )
    assert upload.status_code == 201, upload.text

    usage = client.get(f"/api/v1/workspaces/{wid}/usage", headers=_auth(token))
    assert usage.status_code == 200
    storage = next(
        item for item in usage.json()["items"] if item["metric"] == "storage.bytes"
    )
    assert storage["current"] == 5
    assert storage["unit"] == "bytes"

    client.delete(
        f"/api/v1/files/{upload.json()['id']}",
        headers=_auth(token),
    )
    usage_after_delete = client.get(
        f"/api/v1/workspaces/{wid}/usage", headers=_auth(token)
    )
    storage_after_delete = next(
        item
        for item in usage_after_delete.json()["items"]
        if item["metric"] == "storage.bytes"
    )
    assert storage_after_delete["current"] == 0


def test_plan_and_subscription_endpoints(cleanup_users):
    _uid, token = _reg(cleanup_users)
    r = client.post("/api/v1/workspaces", headers=_auth(token), json={"name": "P"})
    wid = r.json()["id"]
    r = client.get(f"/api/v1/workspaces/{wid}/plan", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["code"] == "free"
    r = client.get(f"/api/v1/workspaces/{wid}/subscription", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "active"
