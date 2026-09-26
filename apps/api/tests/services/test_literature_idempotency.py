"""M23 — Idempotency tests.

Verifies that the context_hash changes when any input that affects
pipeline output changes, and that a completed run for the same hash
+ version is skipped.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.literature import (
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.source import Chunk, Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.literature import context, pipeline


@pytest.fixture(autouse=True)
def _clear_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(LiteratureIntelligenceRun).where(
                LiteratureIntelligenceRun.project_id.in_(pids)
            )
        )
        db.execute(
            delete(ProjectLiteratureItem).where(
                ProjectLiteratureItem.project_id.in_(pids)
            )
        )
        rids = select(Report.id).where(Report.project_id.in_(pids))
        db.execute(
            delete(Chunk).where(
                Chunk.source_id.in_(
                    select(Source.id).where(Source.report_id.in_(rids))
                )
            )
        )
        db.execute(delete(Source).where(Source.report_id.in_(rids)))
        db.execute(delete(Report).where(Report.project_id.in_(pids)))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
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
        db.add(
            User(
                id=uid,
                email=f"lit-id-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _mk_project_with_source(uid) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        r = Report(
            user_id=uid,
            project_id=p.id,
            topic="R",
            output_language="en",
            status="draft",
        )
        db.add(r)
        db.flush()
        s = Source(
            report_id=r.id, title="T", status="metadata_only"
        )
        db.add(s)
        db.commit()
        return p.id, r.id, s.id


def test_same_context_skips(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, _rid, _sid = _mk_project_with_source(uid)

    with SessionLocal() as db:
        r1 = pipeline.run_literature_analysis(
            db, user_id=uid, project_id=pid
        )
    assert r1.run.status == "completed"

    with SessionLocal() as db:
        r2 = pipeline.run_literature_analysis(
            db, user_id=uid, project_id=pid
        )
    assert r2.skipped is True
    assert r2.run.status == "skipped"


def test_new_source_invalidates_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, rid, _sid = _mk_project_with_source(uid)

    with SessionLocal() as db:
        pipeline.run_literature_analysis(
            db, user_id=uid, project_id=pid
        )

    with SessionLocal() as db:
        db.add(
            Source(
                report_id=rid, title="T2", status="metadata_only"
            )
        )
        db.commit()

    with SessionLocal() as db:
        r2 = pipeline.run_literature_analysis(
            db, user_id=uid, project_id=pid
        )
    assert r2.skipped is False
    assert r2.run.status == "completed"


def test_research_question_change_invalidates_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, _rid, _sid = _mk_project_with_source(uid)

    with SessionLocal() as db:
        h1 = context.build_literature_context_hash(
            db, project_id=pid
        )

    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.research_questions = ["What is the effect?"]
        db.commit()

    with SessionLocal() as db:
        h2 = context.build_literature_context_hash(
            db, project_id=pid
        )
    assert h1 != h2


def test_source_metadata_change_invalidates_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, _rid, sid = _mk_project_with_source(uid)

    with SessionLocal() as db:
        h1 = context.build_literature_context_hash(
            db, project_id=pid
        )

    with SessionLocal() as db:
        s = db.get(Source, sid)
        s.citation_count = 42
        s.year = 2024
        db.commit()

    with SessionLocal() as db:
        h2 = context.build_literature_context_hash(
            db, project_id=pid
        )
    assert h1 != h2


def test_screening_override_invalidates_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, _rid, sid = _mk_project_with_source(uid)

    with SessionLocal() as db:
        pipeline.run_literature_analysis(
            db, user_id=uid, project_id=pid
        )
        h1 = context.build_literature_context_hash(
            db, project_id=pid
        )

    with SessionLocal() as db:
        item = db.execute(
            select(ProjectLiteratureItem).where(
                ProjectLiteratureItem.project_id == pid,
                ProjectLiteratureItem.source_id == sid,
            )
        ).scalar_one()
        item.screening_status = "included"
        item.manual_override = True
        from datetime import UTC, datetime

        item.manual_override_at = datetime.now(UTC)
        db.commit()

    with SessionLocal() as db:
        h2 = context.build_literature_context_hash(
            db, project_id=pid
        )
    assert h1 != h2


def test_embedding_change_invalidates_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        r = Report(
            user_id=uid,
            project_id=p.id,
            topic="R",
            output_language="en",
            status="draft",
        )
        db.add(r)
        db.flush()
        s = Source(
            report_id=r.id, title="T", status="full_text"
        )
        db.add(s)
        db.flush()
        c = Chunk(
            source_id=s.id,
            content="text",
            chunk_index=0,
            embedding_status="completed",
            embedding_input_hash="h1",
            embedding_model_version="v1",
        )
        db.add(c)
        db.commit()
        pid = p.id
        cid = c.id

    with SessionLocal() as db:
        h1 = context.build_literature_context_hash(
            db, project_id=pid
        )

    with SessionLocal() as db:
        c = db.get(Chunk, cid)
        c.embedding_input_hash = "h2"
        c.embedding_model_version = "v2"
        db.commit()

    with SessionLocal() as db:
        h2 = context.build_literature_context_hash(
            db, project_id=pid
        )
    assert h1 != h2
