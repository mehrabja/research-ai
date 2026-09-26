"""M19 — ProjectFile service tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.exceptions import (
    DuplicateFile,
    FileNotFound,
    FileTooLarge,
    ProjectArchivedForUpload,
    ProjectNotFound,
)
from app.db.models.jobs import Job
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.report import Report
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.file import FileKind, FileStatus
from app.services import files as files_service
from app.services import projects as projects_service


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


def _mk_user(cleanup_users: list[uuid.UUID]) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"u-{uid.hex[:10]}@example.com",
                password_hash="x",
            )
        )
        db.commit()
    cleanup_users.append(uid)
    return uid


def _chunks(data: bytes) -> Iterator[bytes]:
    yield data


def _upload(db, *, uid, pid, name="f.txt", data=b"hello"):
    return files_service.upload_file(
        db,
        user_id=uid,
        project_id=pid,
        original_filename=name,
        client_mime=None,
        upload_stream=_chunks(data),
    )


def test_upload_minimal(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id)
        assert pf.sha256
        assert pf.size_bytes == 5
        assert pf.file_kind == FileKind.TEXT.value
        assert pf.status == FileStatus.UPLOADED.value
        assert pf.extraction_status == "queued"


def test_upload_unsupported_kind(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(
            db, uid=uid, pid=p.id, name="a.bin", data=b"\x00\x01\x02"
        )
        assert pf.file_kind == FileKind.UNKNOWN.value
        assert pf.extraction_status == "not_supported"


def test_upload_wrong_user(cleanup_users):
    uid_a = _mk_user(cleanup_users)
    uid_b = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid_a, name="A")
        with pytest.raises(ProjectNotFound):
            _upload(db, uid=uid_b, pid=p.id)


def test_upload_archived_project(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        projects_service.archive_project(db, user_id=uid, project_id=p.id)
        with pytest.raises(ProjectArchivedForUpload):
            _upload(db, uid=uid, pid=p.id)


def test_upload_filename_traversal_sanitized(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(
            db, uid=uid, pid=p.id, name="../../etc/passwd", data=b"x"
        )
        assert ".." not in pf.normalized_filename
        assert "/" not in pf.normalized_filename
        assert "\\" not in pf.normalized_filename


def test_upload_dedup_same_content(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"same")
        with pytest.raises(DuplicateFile):
            _upload(db, uid=uid, pid=p.id, name="b.txt", data=b"same")


def test_upload_dedup_after_delete_allows_reupload(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        first = _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"same")
        files_service.delete_file(db, user_id=uid, file_id=first.id)
        second = _upload(db, uid=uid, pid=p.id, name="b.txt", data=b"same")
        assert second.id != first.id
        assert second.sha256 == first.sha256


def test_upload_too_large(cleanup_users, monkeypatch):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        from app.core import config as config_module

        s = config_module.get_settings()
        monkeypatch.setattr(s, "document_max_bytes", 4)
        with pytest.raises(FileTooLarge):
            _upload(db, uid=uid, pid=p.id, data=b"12345")


def test_get_file_wrong_user(cleanup_users):
    uid_a = _mk_user(cleanup_users)
    uid_b = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid_a, name="A")
        pf = _upload(db, uid=uid_a, pid=p.id)
        with pytest.raises(FileNotFound):
            files_service.get_file(db, user_id=uid_b, file_id=pf.id)


def test_list_files_isolated(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"a")
        _upload(db, uid=uid, pid=p.id, name="b.txt", data=b"b")
        rows, total = files_service.list_files(
            db, user_id=uid, project_id=p.id
        )
        assert total == 2


def test_soft_delete_excludes_from_list(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id)
        files_service.delete_file(db, user_id=uid, file_id=pf.id)
        rows, total = files_service.list_files(
            db, user_id=uid, project_id=p.id
        )
        assert total == 0


def test_soft_delete_idempotent(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id)
        a = files_service.delete_file(db, user_id=uid, file_id=pf.id)
        b = files_service.delete_file(db, user_id=uid, file_id=pf.id)
        assert a.deleted_at is not None
        assert a.deleted_at == b.deleted_at


def test_deleted_at_consistency(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id)
        files_service.delete_file(db, user_id=uid, file_id=pf.id)
        assert pf.status == FileStatus.DELETED.value
        assert pf.deleted_at is not None


def test_upload_event_emitted(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id)
        events = (
            db.execute(
                select(ProjectFileEvent).where(
                    ProjectFileEvent.project_file_id == pf.id
                )
            )
            .scalars()
            .all()
        )
        assert [e.event_type for e in events] == ["file_uploaded"]


def test_upload_enqueues_extraction_job(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id)
        jobs = (
            db.execute(
                select(Job).where(Job.project_file_id == pf.id)
            )
            .scalars()
            .all()
        )
        assert len(jobs) == 1
        assert jobs[0].job_type == "file_extract"
        assert jobs[0].idempotency_key == f"file_extract:{pf.id}"


def test_upload_cleanup_on_classify_error(cleanup_users, monkeypatch):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")

        from app.services import files as files_mod

        def boom(*a, **k):
            raise RuntimeError("simulated classify failure")

        monkeypatch.setattr(files_mod, "classify", boom)
        with pytest.raises(RuntimeError):
            _upload(db, uid=uid, pid=p.id, name="x.txt", data=b"x")

        rows = (
            db.execute(
                select(ProjectFile).where(ProjectFile.project_id == p.id)
            )
            .scalars()
            .all()
        )
        assert rows == []
