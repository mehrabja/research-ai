"""M20 — Data Intelligence service tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.data_profile import DataColumnProfile, DataProfile
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services import data_intelligence as data_service
from app.services import files as files_service
from app.services import projects as projects_service
from app.services.file_storage import get_storage_provider


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("FILE_STORAGE_LOCAL_ROOT", str(tmp_path))
    get_settings.cache_clear()
    yield
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
            delete(DataProfile).where(DataProfile.project_file_id.in_(fids))
        )
        db.execute(
            delete(ProjectFileEvent).where(
                ProjectFileEvent.project_file_id.in_(fids)
            )
        )
        db.execute(delete(ProjectFile).where(ProjectFile.id.in_(fids)))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Project).where(Project.user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _mk_user(cleanup_users) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"d-{uid.hex[:10]}@example.com",
                password_hash="x",
            )
        )
        db.commit()
    cleanup_users.append(uid)
    return uid


def _mk_file(db, *, uid, pid, name, data):
    return files_service.upload_file(
        db,
        user_id=uid,
        project_id=pid,
        original_filename=name,
        client_mime=None,
        upload_stream=iter([data]),
    )


def _chunks(pf):
    return get_storage_provider().open(key=pf.storage_key)


def test_csv_profile_basic(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        csv_bytes = b"name,age,score\na,30,1.5\nb,40,2.5\nc,50,3.5\n"
        pf = _mk_file(db, uid=uid, pid=p.id, name="t.csv", data=csv_bytes)
        profile = data_service.profile_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        assert profile.row_count == 3
        assert profile.column_count == 3
        cols = (
            db.execute(
                select(DataColumnProfile)
                .where(DataColumnProfile.data_profile_id == profile.id)
                .order_by(DataColumnProfile.ordinal)
            )
            .scalars()
            .all()
        )
        types = {c.name: c.inferred_type for c in cols}
        assert types["age"] == "integer"
        assert types["score"] == "float"
        age = next(c for c in cols if c.name == "age")
        assert age.mean == pytest.approx(40.0)


def test_csv_null_heavy_column(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        data = b"a,b\n1,\n2,\n3,\n"
        pf = _mk_file(db, uid=uid, pid=p.id, name="n.csv", data=data)
        profile = data_service.profile_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        cols = (
            db.execute(
                select(DataColumnProfile).where(
                    DataColumnProfile.data_profile_id == profile.id
                )
            )
            .scalars()
            .all()
        )
        b_col = next(c for c in cols if c.name == "b")
        assert b_col.null_count == 3
        assert b_col.null_ratio == pytest.approx(1.0)


def test_json_profile_list_of_dicts(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        payload = b'[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]'
        pf = _mk_file(db, uid=uid, pid=p.id, name="t.json", data=payload)
        profile = data_service.profile_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        assert profile.row_count == 2
        assert profile.column_count == 2


def test_json_malformed_sets_failed(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _mk_file(
            db, uid=uid, pid=p.id, name="bad.json", data=b"{not-json"
        )
        profile = data_service.profile_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        assert profile.profile_status == "failed"
        assert profile.profile_error


def test_jsonl_profile(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        payload = b'{"a": 1}\n{"a": 2}\n{"a": 3}\n'
        pf = _mk_file(db, uid=uid, pid=p.id, name="t.jsonl", data=payload)
        profile = data_service.profile_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        assert profile.row_count == 3


def test_profile_file_missing_pf_raises_file_not_found(cleanup_users):
    from app.core.exceptions import FileNotFound

    with SessionLocal() as db:
        missing = uuid.uuid4()
        with pytest.raises(FileNotFound):
            data_service.profile_file(
                db, project_file_id=missing, chunks=iter([b""])
            )
