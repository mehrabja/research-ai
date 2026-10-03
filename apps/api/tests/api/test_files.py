"""M19 — File API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.jobs import Job
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.report import Report
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
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        project_ids = select(Project.id).where(Project.user_id.in_(user_ids))
        file_ids = select(ProjectFile.id).where(
            ProjectFile.project_id.in_(project_ids)
        )
        db.execute(
            delete(ProjectFileEvent).where(
                ProjectFileEvent.project_file_id.in_(file_ids)
            )
        )
        db.execute(delete(Job).where(Job.project_file_id.in_(file_ids)))
        db.execute(delete(ProjectFile).where(ProjectFile.id.in_(file_ids)))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(project_ids))
        )
        db.execute(delete(Report).where(Report.user_id.in_(user_ids)))
        db.execute(delete(Project).where(Project.user_id.in_(user_ids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(user_ids)
            )
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register_and_login(cleanup_users):
    email = f"file-{uuid.uuid4().hex}@example.com"
    pw = "Correct Horse Battery Staple!"
    r = client.post(
        "/api/v1/auth/register", json={"email": email, "password": pw}
    )
    assert r.status_code == 201, r.text
    uid = uuid.UUID(r.json()["id"])
    cleanup_users.append(uid)
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": pw}
    )
    assert r.status_code == 200, r.text
    return uid, r.json()["access_token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _mk_project(token: str, name: str = "P") -> str:
    r = client.post(
        "/api/v1/projects", headers=_auth(token), json={"name": name}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload(token: str, pid: str, name="f.txt", data=b"hello"):
    return client.post(
        f"/api/v1/projects/{pid}/files",
        headers=_auth(token),
        files={"file": (name, data, "application/octet-stream")},
    )


def test_upload_and_get(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    r = _upload(token, pid, "hello.txt", b"hi there")
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    assert r.json()["original_filename"] == "hello.txt"
    assert r.json()["size_bytes"] == 8
    r2 = client.get(f"/api/v1/files/{fid}", headers=_auth(token))
    assert r2.status_code == 200
    assert r2.json()["id"] == fid


def test_list_files(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    _upload(token, pid, "a.txt", b"a")
    _upload(token, pid, "b.txt", b"b")
    r = client.get(f"/api/v1/projects/{pid}/files", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert "folder_id" in data["items"][0]


def test_download_content(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    fid = _upload(token, pid, "x.txt", b"payload").json()["id"]
    r = client.get(f"/api/v1/files/{fid}/content", headers=_auth(token))
    assert r.status_code == 200
    assert r.content == b"payload"


def test_delete_soft(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    fid = _upload(token, pid, "d.txt", b"d").json()["id"]
    r = client.delete(f"/api/v1/files/{fid}", headers=_auth(token))
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/files/{fid}", headers=_auth(token))
    assert r2.status_code == 200
    assert r2.json()["status"] == "deleted"


def test_cross_user_get_404(cleanup_users):
    _, ta = _register_and_login(cleanup_users)
    _, tb = _register_and_login(cleanup_users)
    pid = _mk_project(ta)
    fid = _upload(ta, pid).json()["id"]
    r = client.get(f"/api/v1/files/{fid}", headers=_auth(tb))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "FILE_NOT_FOUND"


def test_cross_user_upload_404(cleanup_users):
    _, ta = _register_and_login(cleanup_users)
    _, tb = _register_and_login(cleanup_users)
    pid = _mk_project(ta)
    r = _upload(tb, pid)
    assert r.status_code == 404


def test_upload_to_archived_project_409(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    client.post(f"/api/v1/projects/{pid}/archive", headers=_auth(token))
    r = _upload(token, pid)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PROJECT_ARCHIVED_FOR_UPLOAD"


def test_duplicate_upload_409(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    _upload(token, pid, "a.txt", b"same")
    r = _upload(token, pid, "b.txt", b"same")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_FILE"


def test_upload_requires_auth(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    r = client.post(
        f"/api/v1/projects/{pid}/files",
        files={"file": ("f.txt", b"x", "text/plain")},
    )
    assert r.status_code == 401


def test_upload_too_large_413(cleanup_users, monkeypatch):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    from app.core import config as config_module

    s = config_module.get_settings()
    monkeypatch.setattr(s, "document_max_bytes", 4)
    r = _upload(token, pid, "big.txt", b"1234567890")
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_list_pagination(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    for i in range(5):
        _upload(token, pid, f"f{i}.txt", f"body-{i}".encode())
    r = client.get(
        f"/api/v1/projects/{pid}/files?limit=2&offset=0",
        headers=_auth(token),
    )
    assert r.json()["total"] == 5
    assert len(r.json()["items"]) == 2
def test_download_content_has_content_length(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    payload = b"payload"
    fid = _upload(token, pid, "x.txt", payload).json()["id"]
    r = client.get(f"/api/v1/files/{fid}/content", headers=_auth(token))
    assert r.status_code == 200
    assert r.headers.get("Content-Length") == str(len(payload))
    assert r.content == payload


def test_move_file_between_folders(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    folder = client.post(
        f"/api/v1/projects/{pid}/file-folders",
        headers={**_auth(token), "Content-Type": "application/json"},
        json={"name": "papers"},
    )
    assert folder.status_code == 201, folder.text
    folder_id = folder.json()["id"]
    fid = _upload(token, pid, "paper.txt", b"paper").json()["id"]

    moved = client.patch(
        f"/api/v1/files/{fid}",
        headers={**_auth(token), "Content-Type": "application/json"},
        json={"folder_id": folder_id},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["folder_id"] == folder_id

    cleared = client.patch(
        f"/api/v1/files/{fid}",
        headers={**_auth(token), "Content-Type": "application/json"},
        json={"folder_id": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["folder_id"] is None


def test_move_file_rejects_foreign_folder(cleanup_users):
    _, ta = _register_and_login(cleanup_users)
    _, tb = _register_and_login(cleanup_users)
    pa = _mk_project(ta)
    pb = _mk_project(tb)
    folder = client.post(
        f"/api/v1/projects/{pb}/file-folders",
        headers={**_auth(tb), "Content-Type": "application/json"},
        json={"name": "other"},
    )
    fid = _upload(ta, pa, "paper.txt", b"paper").json()["id"]
    moved = client.patch(
        f"/api/v1/files/{fid}",
        headers={**_auth(ta), "Content-Type": "application/json"},
        json={"folder_id": folder.json()["id"]},
    )
    assert moved.status_code == 400


def test_list_filter_by_kind(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    _upload(token, pid, "a.txt", b"a")
    _upload(token, pid, "b.bin", b"\x00\x01")
    r = client.get(
        f"/api/v1/projects/{pid}/files?kind=text", headers=_auth(token)
    )
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["file_kind"] == "text"
