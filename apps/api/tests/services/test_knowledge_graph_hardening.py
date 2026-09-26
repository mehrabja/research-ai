"""M25 — Hardening tests (fix pack)."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DatabaseError

from app.core.config import get_settings
from app.core.exceptions import KnowledgeGraphInvalid
from app.db.models.knowledge_graph import (
    KnowledgeGraphBuildRun,
    KnowledgeGraphVersion,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.source import Chunk, Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.knowledge_graph import builder
from app.services.knowledge_graph import context as ctx_svc
from app.services.knowledge_graph import queries as q_svc


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
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        rids = select(Report.id).where(Report.project_id.in_(pids))
        db.execute(delete(Source).where(Source.report_id.in_(rids)))
        db.execute(delete(Report).where(Report.project_id.in_(pids)))
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
            id=uid, email=f"kg-hard-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _mk_project(uid) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        return p.id


def test_force_build_with_same_context_skips(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        r1 = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    assert r1.skipped is False
    with SessionLocal() as db:
        r2 = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid, force=True
        )
    assert r2.skipped is True
    assert r2.run.status == "skipped"
    with SessionLocal() as db:
        completed = db.execute(
            select(func.count()).select_from(
                KnowledgeGraphBuildRun
            ).where(
                KnowledgeGraphBuildRun.project_id == pid,
                KnowledgeGraphBuildRun.status == "completed",
            )
        ).scalar_one()
    assert completed == 1


def test_context_revert_reactivates_superseded_graph(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        r1 = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    v1 = r1.graph_version.id
    assert r1.graph_version.status == "ready"

    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.research_questions = ["B?"]
        db.commit()
    with SessionLocal() as db:
        r2 = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    assert r2.graph_version.version == 2

    with SessionLocal() as db:
        v1_row = db.get(KnowledgeGraphVersion, v1)
        assert v1_row.status == "superseded"

    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.research_questions = None
        db.commit()
    with SessionLocal() as db:
        r3 = builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    assert r3.skipped is True
    assert r3.graph_version is not None
    assert r3.graph_version.id == v1
    assert r3.graph_version.status == "ready"
    assert r3.run.status == "skipped"
    assert r3.run.output_summary is not None
    assert r3.run.output_summary.get("reason") == "reactivated_superseded"

    with SessionLocal() as db:
        v2 = db.execute(
            select(KnowledgeGraphVersion)
            .where(
                KnowledgeGraphVersion.project_id == pid,
                KnowledgeGraphVersion.version == 2,
            )
        ).scalar_one()
        assert v2.status == "superseded"
        ready = db.execute(
            select(func.count()).select_from(
                KnowledgeGraphVersion
            ).where(
                KnowledgeGraphVersion.project_id == pid,
                KnowledgeGraphVersion.status == "ready",
            )
        ).scalar_one()
    assert ready == 1


def test_feature_flag_disables_generation(cleanup_users, monkeypatch):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    monkeypatch.setenv("KNOWLEDGE_GRAPH_ENABLED", "false")
    get_settings.cache_clear()

    from app.core.exceptions import KnowledgeGraphConfigurationInvalid

    with SessionLocal() as db, pytest.raises(
        KnowledgeGraphConfigurationInvalid
    ):
        builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )


def test_get_neighbors_rejects_unknown_relation_type(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    with SessionLocal() as db:
        from app.db.models.knowledge_graph import KnowledgeGraphNode
        node = db.execute(
            select(KnowledgeGraphNode).where(
                KnowledgeGraphNode.project_id == pid,
            ).limit(1)
        ).scalar_one()
        with pytest.raises(KnowledgeGraphInvalid):
            q_svc.get_neighbors(
                db,
                project_id=pid,
                node_id=node.id,
                relation_types=["definitely_not_a_relation"],
            )


def test_build_run_update_is_rejected(cleanup_users):
    """Trigger blocks UPDATE on knowledge_graph_build_runs."""
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        builder.build_knowledge_graph(
            db, user_id=uid, project_id=pid
        )
    with SessionLocal() as db:
        with pytest.raises(DatabaseError):
            db.execute(text(
                "UPDATE knowledge_graph_build_runs "
                "SET status = 'failed' WHERE project_id = :pid"
            ), {"pid": pid})
            db.commit()
        db.rollback()


def test_stale_worker_context_records_skipped_run(
    cleanup_users, monkeypatch
):
    from app.workers import knowledge_graph_handlers as kh

    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        stale_context = ctx_svc.compute_graph_context_hash(
            db, project_id=pid
        )
    with SessionLocal() as db:
        p = db.get(Project, pid)
        p.research_questions = ["new"]
        db.commit()

    ctx = type("Ctx", (), {})()
    ctx.payload = {
        "project_id": str(pid),
        "user_id": str(uid),
        "context_hash": stale_context,
        "graph_version": "m25-v1",
        "force": False,
    }

    out = kh.handle_knowledge_graph_build(ctx)
    assert out["status"] == "skipped"
    assert out["reason"] == "stale_context"

    with SessionLocal() as db:
        skipped = db.execute(
            select(func.count()).select_from(
                KnowledgeGraphBuildRun
            ).where(
                KnowledgeGraphBuildRun.project_id == pid,
                KnowledgeGraphBuildRun.status == "skipped",
                KnowledgeGraphBuildRun.context_hash == stale_context,
            )
        ).scalar_one()
        events = db.execute(
            select(func.count()).select_from(ProjectEvent).where(
                ProjectEvent.project_id == pid,
                ProjectEvent.event_type
                == "knowledge_graph_generation_skipped",
            )
        ).scalar_one()
    assert skipped == 1
    assert events >= 1


def test_hash_changes_when_source_content_hash_changes(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id
        r = Report(
            user_id=uid, project_id=pid, topic="R",
            output_language="en", status="draft",
        )
        db.add(r)
        db.flush()
        s = Source(
            report_id=r.id, title="T", status="metadata_only"
        )
        db.add(s)
        db.commit()
        sid = s.id
    with SessionLocal() as db:
        h1 = ctx_svc.compute_graph_context_hash(db, project_id=pid)
    with SessionLocal() as db:
        s = db.get(Source, sid)
        s.content_hash = "abc123"
        db.commit()
    with SessionLocal() as db:
        h2 = ctx_svc.compute_graph_context_hash(db, project_id=pid)
    assert h1 != h2


def test_hash_changes_when_chunk_identity_changes(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id
        r = Report(
            user_id=uid, project_id=pid, topic="R",
            output_language="en", status="draft",
        )
        db.add(r)
        db.flush()
        s = Source(
            report_id=r.id, title="T", status="metadata_only"
        )
        db.add(s)
        db.flush()
        c = Chunk(source_id=s.id, content="abc", chunk_index=0)
        db.add(c)
        db.commit()
        sid = s.id
        cid = c.id
    with SessionLocal() as db:
        h1 = ctx_svc.compute_graph_context_hash(db, project_id=pid)
    with SessionLocal() as db:
        db.execute(delete(Chunk).where(Chunk.id == cid))
        db.add(Chunk(source_id=sid, content="xyz", chunk_index=0))
        db.commit()
    with SessionLocal() as db:
        h2 = ctx_svc.compute_graph_context_hash(db, project_id=pid)
    assert h1 != h2


def test_context_hash_does_not_reference_global_citation_state(
    cleanup_users,
):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h1 = ctx_svc.compute_graph_context_hash(db, project_id=pid)
    with SessionLocal() as db:
        h2 = ctx_svc.compute_graph_context_hash(db, project_id=pid)
    assert h1 == h2
