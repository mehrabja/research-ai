import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.research_memory import ResearchMemory
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.retrieval_advanced import MemoryType
from app.services import projects as projects_service
from app.services.rag import memory as mem_svc


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            )
        )
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(uids)
            )
        )
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid,
            email=f"rag-mem-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _mk_project(uid) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        return p.id


def test_memory_creation(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        m = mem_svc.upsert_memory(
            db,
            project_id=pid,
            memory_type=MemoryType.QUERY_RESULT.value,
            summary="test",
        )
        db.commit()
    assert m.id is not None


def test_memory_reuse_increments_count(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        mem_svc.upsert_memory(
            db,
            project_id=pid,
            memory_type=MemoryType.QUERY_RESULT.value,
            summary="test",
        )
        db.commit()
    with SessionLocal() as db:
        m2 = mem_svc.upsert_memory(
            db,
            project_id=pid,
            memory_type=MemoryType.QUERY_RESULT.value,
            summary="test",
        )
        db.commit()
    assert int(m2.reuse_count) == 1


def test_memory_project_isolation(cleanup_users):
    u1 = _mk_user(cleanup_users)
    u2 = _mk_user(cleanup_users)
    p1 = _mk_project(u1)
    p2 = _mk_project(u2)
    with SessionLocal() as db:
        mem_svc.upsert_memory(
            db,
            project_id=p1,
            memory_type=MemoryType.QUERY_RESULT.value,
            summary="p1 mem",
        )
        db.commit()
    with SessionLocal() as db:
        rows = db.execute(
            select(ResearchMemory).where(
                ResearchMemory.project_id == p2
            )
        ).scalars().all()
    assert rows == []
