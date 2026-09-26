"""M19 — file_extract worker handler tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.exceptions import StorageUnavailable
from app.db.models.jobs import Job
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.report import Report
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.file import (
    ExtractionStatus,
    FileKind,
    FileStatus,
)
from app.services import files as files_service
from app.services import jobs as jobs_service
from app.services import projects as projects_service
from app.services.file_extraction import extract_bytes
from app.services.file_storage import get_storage_provider
from app.workers.file_handlers import handle_file_extract


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


def _mk_user(cleanup_users) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"w-{uid.hex[:10]}@example.com",
                password_hash="x",
            )
        )
        db.commit()
    cleanup_users.append(uid)
    return uid


def _stream(data: bytes):
    yield data


def _upload(db, *, uid, pid, name, data):
    return files_service.upload_file(
        db,
        user_id=uid,
        project_id=pid,
        original_filename=name,
        client_mime=None,
        upload_stream=_stream(data),
    )


def _make_job(db, *, pf_id, uid, attempt_count=1, max_attempts=3):
    return jobs_service.enqueue_job(
        db,
        job_type="file_extract",
        payload={"file_id": str(pf_id)},
        idempotency_key=f"test:{pf_id}:{uuid.uuid4()}",
        project_file_id=pf_id,
        user_id=uid,
        max_attempts=max_attempts,
    ).job


def test_extract_text_utf8():
    r = extract_bytes(content=b"hello world", kind=FileKind.TEXT, mime=None)
    assert r.supported is True
    assert r.error is None
    assert r.text == "hello world"


def test_extract_text_utf8_bom():
    r = extract_bytes(
        content=b"\xef\xbb\xbfhello", kind=FileKind.TEXT, mime=None
    )
    assert r.supported is True
    assert r.error is None
    assert r.text == "hello"
    assert r.meta["encoding"] == "utf-8-sig"


def test_extract_text_undecodable():
    r = extract_bytes(
        content=b"\xff\xff\xff", kind=FileKind.TEXT, mime=None
    )
    assert r.supported is True
    assert r.error is not None
    assert r.text == ""


def test_extract_html_strips_tags():
    r = extract_bytes(
        content=b"<p>Hello <b>world</b></p>",
        kind=FileKind.DOCUMENT,
        mime="text/html",
    )
    assert r.supported is True
    assert r.text == "Hello world"


def test_extract_unsupported_kind():
    r = extract_bytes(content=b"x", kind=FileKind.IMAGE, mime=None)
    assert r.supported is False


def test_extract_corrupt_pdf_sets_error():
    r = extract_bytes(
        content=b"%PDF-1.4\ncorrupt-body-not-real",
        kind=FileKind.PDF,
        mime="application/pdf",
    )
    assert r.supported is True
    assert r.error is not None


def test_head_probe_bytes_at_least_4096():
    from app.services import files as files_service_mod

    assert files_service_mod._HEAD_PROBE_BYTES >= 4096


def test_handler_success_text(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"hello")
        job = _make_job(db, pf_id=pf.id, uid=uid)

        handle_file_extract(db, job)

        db.refresh(pf)
        assert pf.status == FileStatus.READY.value
        assert pf.extraction_status == ExtractionStatus.COMPLETED.value
        assert pf.extracted_text == "hello"
        assert pf.extraction_error is None


def test_handler_unsupported_kind_completes_ready(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="a.bin", data=b"\x00\x01\x02")
        assert pf.extraction_status == ExtractionStatus.NOT_SUPPORTED.value

        job = _make_job(db, pf_id=pf.id, uid=uid)
        handle_file_extract(db, job)
        db.refresh(pf)
        assert pf.status == FileStatus.READY.value


def _force_extraction_error(monkeypatch):
    from app.workers import file_handlers as fh

    def boom(*a, **k):
        raise RuntimeError("simulated extraction failure")

    monkeypatch.setattr(fh, "extract_bytes", boom)


def test_handler_failure_non_final_keeps_processing(
    cleanup_users, monkeypatch
):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"x")
        job = _make_job(
            db, pf_id=pf.id, uid=uid, attempt_count=1, max_attempts=3
        )
        job.attempt_count = 1
        db.commit()

        _force_extraction_error(monkeypatch)
        with pytest.raises(RuntimeError):
            handle_file_extract(db, job)

        db.refresh(pf)
        assert pf.status == FileStatus.PROCESSING.value
        assert pf.extraction_status == ExtractionStatus.PROCESSING.value


def test_handler_failure_final_marks_failed(cleanup_users, monkeypatch):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"x")
        job = _make_job(
            db, pf_id=pf.id, uid=uid, attempt_count=3, max_attempts=3
        )
        job.attempt_count = 3
        db.commit()

        _force_extraction_error(monkeypatch)
        with pytest.raises(RuntimeError):
            handle_file_extract(db, job)

        db.refresh(pf)
        assert pf.status == FileStatus.FAILED.value
        assert pf.extraction_status == ExtractionStatus.FAILED.value
        assert pf.extraction_error


def test_handler_retry_after_non_final_is_idempotent(
    cleanup_users, monkeypatch
):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"x")
        job = _make_job(
            db, pf_id=pf.id, uid=uid, attempt_count=1, max_attempts=3
        )

        _force_extraction_error(monkeypatch)

        job.attempt_count = 1
        db.commit()
        with pytest.raises(RuntimeError):
            handle_file_extract(db, job)

        job.attempt_count = 2
        db.commit()
        with pytest.raises(RuntimeError):
            handle_file_extract(db, job)

        db.refresh(pf)
        assert pf.status == FileStatus.PROCESSING.value

        job.attempt_count = 3
        db.commit()
        with pytest.raises(RuntimeError):
            handle_file_extract(db, job)

        db.refresh(pf)
        assert pf.status == FileStatus.FAILED.value


def test_attempt_count_semantic_contract_with_m10(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(
            db, uid=uid, pid=p.id, name="a.bin", data=b"\x00\x01\x02"
        )
        assert pf.extraction_status == ExtractionStatus.NOT_SUPPORTED.value

        job = jobs_service.enqueue_job(
            db,
            job_type="file_extract",
            payload={"file_id": str(pf.id)},
            idempotency_key=f"test:{pf.id}:{uuid.uuid4()}",
            project_file_id=pf.id,
            user_id=uid,
            priority=10_000,
            max_attempts=3,
        ).job
        assert job.attempt_count == 0

        claimed = jobs_service.claim_job(db, worker_id="w-test")
        if claimed is None:
            pytest.skip("no claimable job found in shared DB")
        if claimed.id != job.id:
            claimed.status = "queued"
            claimed.attempt_count = 0
            claimed.worker_id = None
            claimed.heartbeat_at = None
            claimed.started_at = None
            db.commit()
            pytest.skip("shared DB had another claimable job")

        assert claimed.attempt_count == 1

        claimed.status = "queued"
        claimed.attempt_count = 0
        claimed.worker_id = None
        claimed.heartbeat_at = None
        claimed.started_at = None
        db.commit()


def test_handler_deleted_file_is_noop(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"x")
        job = _make_job(db, pf_id=pf.id, uid=uid)
        files_service.delete_file(db, user_id=uid, file_id=pf.id)

        handle_file_extract(db, job)

        db.refresh(pf)
        assert pf.status == FileStatus.DELETED.value


def test_handler_deleted_mid_processing_discards_result(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"x")
        files_service.mark_processing(db, file_id=pf.id, user_id=uid)
        files_service.delete_file(db, user_id=uid, file_id=pf.id)

        files_service.apply_extraction_result(
            db,
            file_id=pf.id,
            user_id=uid,
            text="ignored",
            pipeline_version="t",
            meta=None,
            extraction_status="completed",
        )
        db.refresh(pf)
        assert pf.status == FileStatus.DELETED.value
        assert pf.extracted_text is None


def test_handler_missing_storage_raises_and_marks_failed_on_final(
    cleanup_users,
):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="a.txt", data=b"x")
        get_storage_provider().delete(key=pf.storage_key)

        job = _make_job(
            db, pf_id=pf.id, uid=uid, attempt_count=3, max_attempts=3
        )
        job.attempt_count = 3
        db.commit()

        with pytest.raises(StorageUnavailable):
            handle_file_extract(db, job)

        db.refresh(pf)
        assert pf.status == FileStatus.FAILED.value


def test_handler_malformed_payload_raises(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        job = jobs_service.enqueue_job(
            db,
            job_type="file_extract",
            payload={},
            user_id=uid,
        ).job
        with pytest.raises(ValueError):
            handle_file_extract(db, job)


def test_initial_status_pdf_is_queued():
    from app.domain.file import initial_extraction_status

    s = initial_extraction_status(
        FileKind.PDF, detected_mime=None, client_mime=None
    )
    assert s is ExtractionStatus.QUEUED


def test_initial_status_docx_is_not_supported():
    from app.domain.file import initial_extraction_status

    s = initial_extraction_status(
        FileKind.DOCUMENT,
        detected_mime=None,
        client_mime=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
    )
    assert s is ExtractionStatus.NOT_SUPPORTED


def test_initial_status_html_is_queued():
    from app.domain.file import initial_extraction_status

    s = initial_extraction_status(
        FileKind.DOCUMENT,
        detected_mime="text/html",
        client_mime=None,
    )
    assert s is ExtractionStatus.QUEUED
