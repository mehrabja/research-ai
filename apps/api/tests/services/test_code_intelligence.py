"""M20 — Code Intelligence service tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.code_analysis import (
    CodeAnalysis,
    CodeSymbol,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.user import User
from app.db.session import SessionLocal
from app.domain.code_intelligence import ParseStatus
from app.services import code_intelligence as code_service
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
            delete(CodeAnalysis).where(
                CodeAnalysis.project_file_id.in_(fids)
            )
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
                email=f"c-{uid.hex[:10]}@example.com",
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


def test_python_analysis_extracts_symbols(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        src = (
            "import os\n"
            "from typing import Any\n"
            "\n"
            "CONST = 42\n"
            "\n"
            "class Foo:\n"
            "    def bar(self, x: int) -> int:\n"
            "        return x + 1\n"
            "\n"
            "def baz(a, b):\n"
            "    return a + b\n"
        )
        pf = _mk_file(db, uid=uid, pid=p.id, name="m.py", data=src.encode())
        analysis = code_service.analyze_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        assert analysis.parse_status == ParseStatus.COMPLETED.value
        assert analysis.function_count == 2
        assert analysis.class_count == 1
        assert analysis.import_count == 2
        symbols = db.execute(
            select(CodeSymbol).where(
                CodeSymbol.code_analysis_id == analysis.id
            )
        ).scalars().all()
        names = {s.name for s in symbols}
        assert "Foo" in names and "bar" in names and "baz" in names
        assert "CONST" in names


def test_python_syntax_error_sets_failed_status(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _mk_file(db, uid=uid, pid=p.id, name="bad.py", data=b"def (:\n")
        analysis = code_service.analyze_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        assert analysis.parse_status == ParseStatus.FAILED.value
        assert analysis.parse_error


def test_js_fallback_extracts_imports(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        src = (
            "import x from 'mod';\n"
            "require('other');\n"
            "function f() {}\n"
            "class C {}\n"
        )
        pf = _mk_file(db, uid=uid, pid=p.id, name="m.js", data=src.encode())
        analysis = code_service.analyze_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        assert analysis.import_count == 2
        assert analysis.function_count >= 1
        assert analysis.class_count >= 1


def test_analysis_replace_latest(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _mk_file(db, uid=uid, pid=p.id, name="m.py", data=b"def a(): pass\n")
        a1 = code_service.analyze_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        a2 = code_service.analyze_file(
            db, project_file_id=pf.id, chunks=_chunks(pf)
        )
        assert a1.id == a2.id


def test_analyze_file_missing_pf_raises_file_not_found(cleanup_users):
    from app.core.exceptions import FileNotFound

    with SessionLocal() as db:
        missing = uuid.uuid4()
        with pytest.raises(FileNotFound):
            code_service.analyze_file(
                db, project_file_id=missing, chunks=iter([b""])
            )


def test_analyze_file_unsupported_language(cleanup_users):
    from app.core.exceptions import CodeAnalysisUnsupportedLanguage

    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        pf = _mk_file(db, uid=uid, pid=p.id, name="X.go", data=b"package x")
        with pytest.raises(CodeAnalysisUnsupportedLanguage):
            code_service.analyze_file(
                db, project_file_id=pf.id, chunks=_chunks(pf)
            )
