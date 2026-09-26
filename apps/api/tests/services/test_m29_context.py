"""M29 — deterministic, content-based context hash."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.technical_intelligence import context as ctx_svc


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = [
            r[0]
            for r in db.execute(
                select(Project.id).where(Project.user_id.in_(uids))
            ).all()
        ]
        if pids:
            db.execute(delete(ProjectFile).where(
                ProjectFile.project_id.in_(pids)
            ))
            db.execute(delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            ))
            db.execute(delete(Project).where(Project.id.in_(pids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(uids)
            )
        )
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids: list[uuid.UUID]) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid,
            email=f"m29ctx-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _mk_project(uid: uuid.UUID) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science",
        )
        return p.id


def _mk_file(
    project_id: uuid.UUID, *, sha256: str, uploaded_by: uuid.UUID,
) -> uuid.UUID:
    fid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(ProjectFile(
            id=fid,
            project_id=project_id,
            uploaded_by=uploaded_by,
            original_filename="data.csv",
            normalized_filename="data.csv",
            extension=".csv",
            storage_key=f"k/{fid}",
            storage_provider="local",
            size_bytes=100,
            sha256=sha256,
            client_mime_type="text/csv",
            file_kind="structured_data",
            status="ready",
        ))
        db.commit()
    return fid


def test_hash_is_deterministic(cleanup_users) -> None:
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h1 = ctx_svc.compute_m29_context_hash(db, project_id=pid)
        h2 = ctx_svc.compute_m29_context_hash(db, project_id=pid)
    assert h1 == h2
    assert len(h1) == 64


def test_hash_differs_per_project(cleanup_users) -> None:
    uid = _mk_user(cleanup_users)
    p1 = _mk_project(uid)
    p2 = _mk_project(uid)
    with SessionLocal() as db:
        h1 = ctx_svc.compute_m29_context_hash(db, project_id=p1)
        h2 = ctx_svc.compute_m29_context_hash(db, project_id=p2)
    assert h1 != h2


def test_hash_changes_when_file_content_changes(cleanup_users) -> None:
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    fid = _mk_file(pid, sha256="a" * 64, uploaded_by=uid)
    with SessionLocal() as db:
        h1 = ctx_svc.compute_m29_context_hash(db, project_id=pid)
    with SessionLocal() as db:
        pf = db.get(ProjectFile, fid)
        assert pf is not None
        pf.sha256 = "b" * 64
        db.commit()
    with SessionLocal() as db:
        h2 = ctx_svc.compute_m29_context_hash(db, project_id=pid)
    assert h1 != h2


def test_hash_changes_when_file_added(cleanup_users) -> None:
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h1 = ctx_svc.compute_m29_context_hash(db, project_id=pid)
    _mk_file(pid, sha256="a" * 64, uploaded_by=uid)
    with SessionLocal() as db:
        h2 = ctx_svc.compute_m29_context_hash(db, project_id=pid)
    assert h1 != h2
