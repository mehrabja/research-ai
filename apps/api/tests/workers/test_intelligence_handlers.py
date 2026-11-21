"""M20 — Worker handler tests for code_analyze and data_profile."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.exceptions import (
    CodeAnalysisUnsupportedLanguage,
    StorageUnavailable,
)
from app.db.models.code_analysis import (
    CodeAnalysis,
)
from app.db.models.data_profile import DataProfile
from app.db.models.jobs import Job
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.report import Report
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.code_intelligence import ParseStatus
from app.domain.jobs import JobContext
from app.services import files as files_service
from app.services import jobs as jobs_service
from app.services import projects as projects_service
from app.services.file_storage import get_storage_provider
from app.workers.intelligence_handlers import (
    handle_code_analyze,
    handle_data_profile,
)


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
                email=f"wh-{uid.hex[:10]}@example.com",
                password_hash="x",
            )
        )
        db.commit()
    cleanup_users.append(uid)
    return uid


def _upload(db, *, uid, pid, name, data):
    return files_service.upload_file(
        db,
        user_id=uid,
        project_id=pid,
        original_filename=name,
        client_mime=None,
        upload_stream=iter([data]),
    )


def _ctx(job: Job) -> JobContext:
    return JobContext(
        job_id=job.id,
        job_type=job.job_type,
        attempt_count=job.attempt_count,
        worker_id="w-test",
        payload=dict(job.payload or {}),
    )


def _enqueue(db, *, pf_id, uid, job_type):
    key = f"{job_type}:{pf_id}:{uuid.uuid4()}"
    return jobs_service.enqueue_job(
        db,
        job_type=job_type,
        payload={"file_id": str(pf_id)},
        idempotency_key=key,
        project_file_id=pf_id,
        user_id=uid,
    ).job


def test_code_analyze_happy_path(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(
            db,
            uid=uid,
            pid=p.id,
            name="m.py",
            data=b"def f():\n    return 1\nclass C:\n    pass\n",
        )
        job = _enqueue(db, pf_id=pf.id, uid=uid, job_type="code_analyze")
        handle_code_analyze(_ctx(job))
        analysis = db.execute(
            select(CodeAnalysis).where(CodeAnalysis.project_file_id == pf.id)
        ).scalar_one()
        assert analysis.parse_status == ParseStatus.COMPLETED.value
        assert analysis.function_count == 1
        assert analysis.class_count == 1



def test_notebook_upload_runs_static_code_analysis(cleanup_users):
    import json

    uid = _mk_user(cleanup_users)
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"name": "python3", "language": "python"},
            "language_info": {"name": "python"},
        },
        "cells": [
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"text/plain": "PRIVATE_NOTEBOOK_OUTPUT"},
                    }
                ],
                "source": [
                    "import math\n",
                    "def area(radius):\n",
                    "    return math.pi * radius * radius\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": "# Research notes",
            },
        ],
    }
    raw = json.dumps(notebook).encode("utf-8")

    with SessionLocal() as db:
        project = projects_service.create_project(
            db, user_id=uid, name="Notebook project"
        )
        pf = _upload(
            db,
            uid=uid,
            pid=project.id,
            name="analysis.ipynb",
            data=raw,
        )
        assert pf.file_kind == "code"
        job = db.execute(
            select(Job).where(
                Job.project_file_id == pf.id,
                Job.job_type == "code_analyze",
            )
        ).scalar_one()
        handle_code_analyze(_ctx(job))

        analysis = db.execute(
            select(CodeAnalysis).where(
                CodeAnalysis.project_file_id == pf.id
            )
        ).scalar_one()
        assert analysis.language == "notebook"
        assert analysis.parse_status == ParseStatus.COMPLETED.value
        assert analysis.function_count == 1
        assert analysis.import_count == 1
        notebook_meta = analysis.analysis_meta["notebook"]
        assert notebook_meta["execution_performed"] is False
        assert notebook_meta["cell_count_total"] == 2
        assert notebook_meta["cell_type_counts"]["markdown"] == 1
        assert notebook_meta["outputs"]["output_payloads_stored"] is False
        assert "PRIVATE_NOTEBOOK_OUTPUT" not in str(analysis.analysis_meta)

def test_code_analyze_deleted_file_noop(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="m.py", data=b"x=1\n")
        job = _enqueue(db, pf_id=pf.id, uid=uid, job_type="code_analyze")
        files_service.delete_file(db, user_id=uid, file_id=pf.id)
        handle_code_analyze(_ctx(job))
        analysis = db.execute(
            select(CodeAnalysis).where(CodeAnalysis.project_file_id == pf.id)
        ).scalar_one_or_none()
        assert analysis is None


def test_code_analyze_missing_storage_raises(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="m.py", data=b"x=1\n")
        job = _enqueue(db, pf_id=pf.id, uid=uid, job_type="code_analyze")
        get_storage_provider().delete(key=pf.storage_key)
        with pytest.raises(StorageUnavailable):
            handle_code_analyze(_ctx(job))


def test_code_analyze_malformed_payload_raises(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        job = jobs_service.enqueue_job(
            db,
            job_type="code_analyze",
            payload={},
            user_id=uid,
        ).job
        with pytest.raises(ValueError):
            handle_code_analyze(_ctx(job))


def test_code_analyze_idempotent_rerun(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="m.py", data=b"def f(): pass\n")
        job = _enqueue(db, pf_id=pf.id, uid=uid, job_type="code_analyze")
        handle_code_analyze(_ctx(job))
        job2 = _enqueue(db, pf_id=pf.id, uid=uid, job_type="code_analyze")
        handle_code_analyze(_ctx(job2))
        rows = (
            db.execute(
                select(CodeAnalysis).where(
                    CodeAnalysis.project_file_id == pf.id
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1


def test_code_analyze_unsupported_language_rejected(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="X.java", data=b"class X {}")
        job = _enqueue(db, pf_id=pf.id, uid=uid, job_type="code_analyze")
        with pytest.raises(CodeAnalysisUnsupportedLanguage):
            handle_code_analyze(_ctx(job))
        analysis = db.execute(
            select(CodeAnalysis).where(CodeAnalysis.project_file_id == pf.id)
        ).scalar_one_or_none()
        assert analysis is None


def test_data_profile_happy_path(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(
            db,
            uid=uid,
            pid=p.id,
            name="t.csv",
            data=b"a,b\n1,x\n2,y\n3,z\n",
        )
        job = _enqueue(db, pf_id=pf.id, uid=uid, job_type="data_profile")
        handle_data_profile(_ctx(job))
        profile = db.execute(
            select(DataProfile).where(DataProfile.project_file_id == pf.id)
        ).scalar_one()
        assert profile.row_count == 3
        assert profile.column_count == 2
        assert profile.quality is not None
        assert profile.quality.get("rows_scanned") == 3
        assert profile.quality.get("scan_truncated") is False


def test_data_profile_deleted_file_noop(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="t.csv", data=b"a\n1\n")
        job = _enqueue(db, pf_id=pf.id, uid=uid, job_type="data_profile")
        files_service.delete_file(db, user_id=uid, file_id=pf.id)
        handle_data_profile(_ctx(job))
        profile = db.execute(
            select(DataProfile).where(DataProfile.project_file_id == pf.id)
        ).scalar_one_or_none()
        assert profile is None


def test_data_profile_malformed_payload_raises(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        job = jobs_service.enqueue_job(
            db,
            job_type="data_profile",
            payload={},
            user_id=uid,
        ).job
        with pytest.raises(ValueError):
            handle_data_profile(_ctx(job))


def test_data_profile_idempotent_rerun(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _upload(db, uid=uid, pid=p.id, name="t.csv", data=b"a\n1\n")
        job = _enqueue(db, pf_id=pf.id, uid=uid, job_type="data_profile")
        handle_data_profile(_ctx(job))
        job2 = _enqueue(db, pf_id=pf.id, uid=uid, job_type="data_profile")
        handle_data_profile(_ctx(job2))
        rows = (
            db.execute(
                select(DataProfile).where(DataProfile.project_file_id == pf.id)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
