"""M20 — Intelligence API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.code_analysis import CodeAnalysis
from app.db.models.data_profile import DataProfile
from app.db.models.jobs import Job
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.report import Report
from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services import code_intelligence as code_service
from app.services import data_intelligence as data_service
from app.services.file_storage import get_storage_provider
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
        pids = select(Project.id).where(Project.user_id.in_(user_ids))
        fids = select(ProjectFile.id).where(ProjectFile.project_id.in_(pids))
        db.execute(
            delete(CodeAnalysis).where(
                CodeAnalysis.project_file_id.in_(fids)
            )
        )
        db.execute(
            delete(DataProfile).where(DataProfile.project_file_id.in_(fids))
        )
        db.execute(
            delete(ProjectFileEvent).where(
                ProjectFileEvent.project_file_id.in_(fids)
            )
        )
        db.execute(delete(Job).where(Job.project_file_id.in_(fids)))
        db.execute(delete(ProjectFile).where(ProjectFile.id.in_(fids)))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Report).where(Report.user_id.in_(user_ids)))
        db.execute(delete(Project).where(Project.user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register_and_login(cleanup_users):
    email = f"int-{uuid.uuid4().hex}@example.com"
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
    return uid, r.json()["access_token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _mk_project(token) -> str:
    r = client.post(
        "/api/v1/projects", headers=_auth(token), json={"name": "P"}
    )
    return r.json()["id"]


def _upload(token, pid, name, data, mime="text/plain"):
    return client.post(
        f"/api/v1/projects/{pid}/files",
        headers=_auth(token),
        files={"file": (name, data, mime)},
    )


def _run_code_analysis(file_id):
    with SessionLocal() as db:
        pf = db.get(ProjectFile, uuid.UUID(file_id))
        provider = get_storage_provider()
        code_service.analyze_file(
            db,
            project_file_id=pf.id,
            chunks=provider.open(key=pf.storage_key),
        )


def _run_data_profile(file_id):
    with SessionLocal() as db:
        pf = db.get(ProjectFile, uuid.UUID(file_id))
        provider = get_storage_provider()
        data_service.profile_file(
            db,
            project_file_id=pf.id,
            chunks=provider.open(key=pf.storage_key),
        )


def test_code_analysis_ownership(cleanup_users):
    _, ta = _register_and_login(cleanup_users)
    _, tb = _register_and_login(cleanup_users)
    pid = _mk_project(ta)
    fid = _upload(ta, pid, "m.py", b"def f(): pass\n").json()["id"]
    _run_code_analysis(fid)
    r = client.get(f"/api/v1/files/{fid}/code-analysis", headers=_auth(tb))
    assert r.status_code == 404


def test_code_analysis_happy_path(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    fid = _upload(
        token, pid, "m.py", b"def f(): pass\nclass C: pass\n"
    ).json()["id"]
    _run_code_analysis(fid)
    r = client.get(
        f"/api/v1/files/{fid}/code-analysis", headers=_auth(token)
    )
    assert r.status_code == 200
    assert r.json()["function_count"] == 1
    assert r.json()["class_count"] == 1


def test_code_symbols_pagination(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    src = b"\n".join(f"def f{i}(): pass".encode() for i in range(20))
    fid = _upload(token, pid, "m.py", src).json()["id"]
    _run_code_analysis(fid)
    r = client.get(
        f"/api/v1/files/{fid}/code-symbols?limit=5&offset=0",
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) == 5
    assert r.json()["total"] == 20


def test_code_analysis_not_found(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    fid = _upload(token, pid, "m.bin", b"\x00").json()["id"]
    r = client.get(
        f"/api/v1/files/{fid}/code-analysis", headers=_auth(token)
    )
    assert r.status_code == 404


def test_data_profile_happy_path(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    fid = _upload(
        token, pid, "t.csv", b"a,b\n1,x\n2,y\n", mime="text/csv"
    ).json()["id"]
    _run_data_profile(fid)
    r = client.get(
        f"/api/v1/files/{fid}/data-profile", headers=_auth(token)
    )
    assert r.status_code == 200
    assert r.json()["row_count"] == 2
    assert r.json()["column_count"] == 2


def test_data_columns_list(cleanup_users):
    _, token = _register_and_login(cleanup_users)
    pid = _mk_project(token)
    fid = _upload(
        token, pid, "t.csv", b"a,b\n1,x\n2,y\n", mime="text/csv"
    ).json()["id"]
    _run_data_profile(fid)
    r = client.get(
        f"/api/v1/files/{fid}/data-columns", headers=_auth(token)
    )
    assert r.status_code == 200
    assert r.json()["total"] == 2
