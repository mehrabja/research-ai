"""M36 — cross-tenant isolation tests.

Verifies User A cannot access User B's resources. The repository
convention is to return 404 (not 403) for unauthorized cross-user
access. These tests enforce that convention.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register_and_token() -> tuple[str, str]:
    email = f"m36-ct-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-12345"},
    )
    assert r.status_code in (200, 201), r.text
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-horse-12345"},
    )
    assert r.status_code == 200, r.text
    return email, r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mk_project(token: str, name: str = "x") -> str:
    r = client.post(
        "/api/v1/projects",
        json={"name": name},
        headers=_auth(token),
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _mk_report(token: str, project_id: str) -> str:
    r = client.post(
        "/api/v1/reports",
        json={
            "project_id": project_id,
            "topic": "t",
            "output_language": "en",
        },
        headers=_auth(token),
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _upload_file(token: str, project_id: str) -> str:
    r = client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("x.txt", b"payload", "text/plain")},
        headers=_auth(token),
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_a_cannot_read_b_project() -> None:
    _, token_a = _register_and_token()
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")

    r = client.get(
        f"/api/v1/projects/{pid_b}", headers=_auth(token_a)
    )
    assert r.status_code == 404


def test_a_cannot_patch_b_project() -> None:
    _, token_a = _register_and_token()
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")

    r = client.patch(
        f"/api/v1/projects/{pid_b}",
        json={"name": "stolen"},
        headers=_auth(token_a),
    )
    assert r.status_code == 404


def test_a_cannot_read_b_report() -> None:
    _, token_a = _register_and_token()
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")
    rid_b = _mk_report(token_b, pid_b)

    r = client.get(
        f"/api/v1/reports/{rid_b}", headers=_auth(token_a)
    )
    assert r.status_code == 404


def test_a_cannot_delete_b_report() -> None:
    _, token_a = _register_and_token()
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")
    rid_b = _mk_report(token_b, pid_b)

    r = client.delete(
        f"/api/v1/reports/{rid_b}", headers=_auth(token_a)
    )
    assert r.status_code == 404


def test_a_cannot_read_b_file_metadata() -> None:
    _, token_a = _register_and_token()
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")
    fid_b = _upload_file(token_b, pid_b)

    r = client.get(
        f"/api/v1/files/{fid_b}", headers=_auth(token_a)
    )
    assert r.status_code == 404


def test_a_cannot_download_b_file() -> None:
    _, token_a = _register_and_token()
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")
    fid_b = _upload_file(token_b, pid_b)

    r = client.get(
        f"/api/v1/files/{fid_b}/content", headers=_auth(token_a)
    )
    assert r.status_code == 404


def test_a_cannot_list_b_project_files() -> None:
    _, token_a = _register_and_token()
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")
    _upload_file(token_b, pid_b)

    r = client.get(
        f"/api/v1/projects/{pid_b}/files", headers=_auth(token_a)
    )
    assert r.status_code == 404


def test_anonymous_cannot_read_project() -> None:
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")

    r = client.get(f"/api/v1/projects/{pid_b}")
    assert r.status_code == 401


def test_garbage_token_rejected() -> None:
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")

    r = client.get(
        f"/api/v1/projects/{pid_b}",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert r.status_code == 401


def test_a_cannot_access_b_orchestration_run() -> None:
    _, token_a = _register_and_token()
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")
    rid_b = _mk_report(token_b, pid_b)

    # Ask for the current orchestration run of B's report.
    r = client.get(
        f"/api/v1/reports/{rid_b}/orchestration/current",
        headers=_auth(token_a),
    )
    assert r.status_code == 404


def test_a_cannot_list_b_orchestration_runs() -> None:
    _, token_a = _register_and_token()
    _, token_b = _register_and_token()
    pid_b = _mk_project(token_b, "b-only")
    rid_b = _mk_report(token_b, pid_b)

    r = client.get(
        f"/api/v1/reports/{rid_b}/orchestration/runs",
        headers=_auth(token_a),
    )
    assert r.status_code == 404
