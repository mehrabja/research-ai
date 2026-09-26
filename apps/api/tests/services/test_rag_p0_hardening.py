"""M26 — P0 hardening regression tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select, text

from app.core.config import get_settings
from app.core.exceptions import (
    EmbeddingsNotReadyError,
    RetrievalConfigurationError,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.source import Chunk, Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.embeddings import EmbeddingProfile
from app.services import projects as projects_service
from app.services.rag import candidates as cand_svc
from app.services.rag import context_hash as ch_svc
from app.services.rag import graph_expansion as gx_svc
from app.services.rag.candidates import Candidate


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
            delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            )
        )
        rids = select(Report.id).where(Report.project_id.in_(pids))
        db.execute(delete(Chunk).where(Chunk.source_id.in_(
            select(Source.id).where(Source.report_id.in_(rids))
        )))
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
            id=uid,
            email=f"rag-p0-{uid.hex[:8]}@e.com",
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


def _dummy_provider():
    class _P:
        def embed_query(self, text: str) -> list[float]:
            return [0.0] * 1536

    return _P()


def _dummy_profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="openai",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
        profile_version="m9.1",
    )


def test_generate_candidates_propagates_embeddings_not_ready(monkeypatch):
    from app.services import retrieval as retrieval_svc

    def _boom(*a, **k):
        raise EmbeddingsNotReadyError("no embeddings")

    monkeypatch.setattr(retrieval_svc, "retrieve_project_scope", _boom)
    with pytest.raises(EmbeddingsNotReadyError):
        cand_svc.generate_candidates(
            None,  # type: ignore[arg-type]
            user_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            query="q",
            mode="lexical",
            algorithm="ann",
            limit=10,
            allowed_source_ids=None,
            provider=_dummy_provider(),
            profile=_dummy_profile(),
        )


def test_generate_candidates_propagates_config_error(monkeypatch):
    from app.services import retrieval as retrieval_svc

    def _boom(*a, **k):
        raise RetrievalConfigurationError("bad config")

    monkeypatch.setattr(retrieval_svc, "retrieve_project_scope", _boom)
    with pytest.raises(RetrievalConfigurationError):
        cand_svc.generate_candidates(
            None,  # type: ignore[arg-type]
            user_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            query="q",
            mode="lexical",
            algorithm="ann",
            limit=10,
            allowed_source_ids=None,
            provider=_dummy_provider(),
            profile=_dummy_profile(),
        )


def _hash_with(db, pid, **overrides):
    base = {
        "project_id": pid,
        "report_id": None,
        "query_hash": "qhash",
        "graph_version_id": None,
        "plan_id": None,
        "section_id": None,
        "requirement_id": None,
        "mode": "lexical",
        "algorithm": "ann",
        "filters": {"mode": "lexical"},
        "profile": _dummy_profile(),
        "effective_graph_enabled": True,
        "effective_memory_enabled": True,
        "effective_diversity_enabled": True,
        "effective_max_results": 10,
        "candidate_limit": 40,
    }
    base.update(overrides)
    return ch_svc.compute_retrieval_context_hash(db, **base)


@pytest.mark.parametrize("field,alt_value", [
    ("effective_graph_enabled", False),
    ("effective_memory_enabled", False),
    ("effective_diversity_enabled", False),
    ("effective_max_results", 20),
    ("candidate_limit", 80),
])
def test_effective_config_changes_hash(cleanup_users, field, alt_value):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h1 = _hash_with(db, pid)
        h2 = _hash_with(db, pid, **{field: alt_value})
    assert h1 != h2


def test_content_change_invalidates_hash_without_reembedding(
    cleanup_users,
):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        r = Report(
            user_id=uid, project_id=pid, topic="t",
            output_language="en", status="draft",
        )
        db.add(r)
        db.flush()
        s = Source(
            report_id=r.id, title="a",
            status="full_text", year=2020,
        )
        db.add(s)
        db.flush()
        c = Chunk(
            source_id=s.id, content="one",
            chunk_index=0, char_end=3,
        )
        db.add(c)
        db.commit()
        cid = c.id

    with SessionLocal() as db:
        h1 = _hash_with(db, pid)

    with SessionLocal() as db:
        db.execute(
            text("UPDATE chunks SET content = 'two' WHERE id = :id"),
            {"id": cid},
        )
        db.commit()

    with SessionLocal() as db:
        h2 = _hash_with(db, pid)

    assert h1 != h2


def test_graph_unexpected_error_propagates(cleanup_users, monkeypatch):
    from app.db.models.knowledge_graph import KnowledgeGraphNode
    from app.services.knowledge_graph import queries as kg_queries

    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        r = Report(
            user_id=uid, project_id=pid, topic="t",
            output_language="en", status="draft",
        )
        db.add(r)
        db.flush()
        s = Source(
            report_id=r.id, title="a",
            status="full_text", year=2020,
        )
        db.add(s)
        db.flush()
        db.add(Chunk(source_id=s.id, content="one",
                     chunk_index=0, char_end=3))
        db.commit()
        sid, rid = s.id, r.id

    from app.db.models.knowledge_graph import KnowledgeGraphVersion

    with SessionLocal() as db:
        gv = KnowledgeGraphVersion(
            project_id=pid,
            version=1,
            status="ready",
            graph_version="m25-v1",
            context_hash=f"test-{uuid.uuid4().hex[:12]}",
        )
        db.add(gv)
        db.flush()
        gv_id = gv.id

        node = KnowledgeGraphNode(
            graph_version_id=gv_id,
            project_id=pid,
            node_type="source",
            node_key=f"source:{sid}",
            entity_id=sid,
            label=None,
        )
        db.add(node)
        db.commit()

    def _boom(*a, **k):
        raise RuntimeError("graph exploded")

    monkeypatch.setattr(kg_queries, "bounded_traversal", _boom)

    seed = Candidate(
        chunk_id=uuid.uuid4(),
        source_id=sid,
        report_id=rid,
        chunk_index=0,
        vector_distance=None,
        vector_rank=None,
        lexical_score=None,
        lexical_rank=None,
        fusion_score=0.5,
        stage="hybrid",
    )

    with SessionLocal() as db, pytest.raises(RuntimeError):
        gx_svc.expand_candidates(
            db,
            project_id=pid,
            graph_version_id=gv_id,
            seed_candidates=[seed],
            max_depth=2,
            max_nodes=20,
        )
