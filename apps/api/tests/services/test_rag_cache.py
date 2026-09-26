"""M26 — Stage C: cache + lock tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.embeddings import EmbeddingProfile
from app.services import projects as projects_service
from app.services.rag import context as ctx_svc
from app.services.rag import graph_context as gc_svc


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
            id=uid, email=f"rag-cache-{uid.hex[:8]}@e.com",
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


def _provider():
    class _P:
        def embed_query(self, text: str) -> list[float]:
            return [0.0] * 1536

    return _P()


def _profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="openai",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
        profile_version="m9.1",
    )


def test_lock_key_deterministic_same_project_and_hash():
    pid = uuid.uuid4()
    k1 = ctx_svc.compute_context_lock_key(
        project_id=pid, context_hash="abc"
    )
    k2 = ctx_svc.compute_context_lock_key(
        project_id=pid, context_hash="abc"
    )
    assert k1 == k2


def test_lock_key_differs_for_different_hash():
    pid = uuid.uuid4()
    k1 = ctx_svc.compute_context_lock_key(
        project_id=pid, context_hash="abc"
    )
    k2 = ctx_svc.compute_context_lock_key(
        project_id=pid, context_hash="xyz"
    )
    assert k1 != k2


def test_lock_key_differs_for_different_project():
    k1 = ctx_svc.compute_context_lock_key(
        project_id=uuid.uuid4(), context_hash="abc"
    )
    k2 = ctx_svc.compute_context_lock_key(
        project_id=uuid.uuid4(), context_hash="abc"
    )
    assert k1 != k2


def _isolate_pipeline(monkeypatch) -> None:
    from app.services.rag import candidates as cand_mod
    from app.services.rag import decomposition as dec_mod
    from app.services.rag import diversity as div_mod
    from app.services.rag import memory as mem_mod
    from app.services.rag import orchestrator as orch_mod
    from app.services.rag import plan_filter as plan_mod
    from app.services.rag import scoring as score_mod

    monkeypatch.setattr(
        dec_mod, "decompose_deterministic", lambda q: []
    )
    monkeypatch.setattr(
        cand_mod, "generate_candidates",
        lambda *a, **k: ([], {}, []),
    )
    monkeypatch.setattr(
        plan_mod, "apply_plan_filters",
        lambda raw, **k: (raw, []),
    )
    monkeypatch.setattr(
        score_mod, "score_candidates",
        lambda raw, **k: [],
    )
    monkeypatch.setattr(
        div_mod, "apply_mmr",
        lambda scored, **k: [],
    )
    monkeypatch.setattr(
        mem_mod, "list_active_memories",
        lambda *a, **k: [],
    )
    monkeypatch.setattr(
        mem_mod, "learn_from_run",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        orch_mod, "_apply_memory_hints",
        lambda *a, **k: None,
    )


def test_second_call_returns_cached_run(cleanup_users, monkeypatch):
    _isolate_pipeline(monkeypatch)
    from app.services.rag import orchestrator as orch

    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        ctx = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            mode="lexical",
        )
        outcome1 = orch.retrieve_research_context(
            db,
            request=orch.RetrievalRequest(
                project_id=pid, user_id=uid, query="x",
                provider=_provider(), profile=_profile(),
                mode="lexical",
            ),
            context=ctx,
        )

    with SessionLocal() as db:
        ctx2 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            mode="lexical",
        )
        outcome2 = orch.retrieve_research_context(
            db,
            request=orch.RetrievalRequest(
                project_id=pid, user_id=uid, query="x",
                provider=_provider(), profile=_profile(),
                mode="lexical",
            ),
            context=ctx2,
        )

    assert outcome2.cached is True
    assert outcome1.run.id == outcome2.run.id


def test_failed_run_not_reused(cleanup_users, monkeypatch):
    _isolate_pipeline(monkeypatch)
    from app.db.models.retrieval import RetrievalRun
    from app.services.rag import orchestrator as orch

    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        ctx = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            mode="lexical",
        )
        orch.retrieve_research_context(
            db,
            request=orch.RetrievalRequest(
                project_id=pid, user_id=uid, query="x",
                provider=_provider(), profile=_profile(),
                mode="lexical",
            ),
            context=ctx,
        )

    with SessionLocal() as db:
        run = db.execute(
            select(RetrievalRun).where(
                RetrievalRun.project_id == pid
            )
        ).scalar_one()
        run.status = "failed"
        db.commit()

    with SessionLocal() as db:
        ctx2 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            mode="lexical",
        )
        outcome2 = orch.retrieve_research_context(
            db,
            request=orch.RetrievalRequest(
                project_id=pid, user_id=uid, query="x",
                provider=_provider(), profile=_profile(),
                mode="lexical",
            ),
            context=ctx2,
        )
    assert outcome2.cached is False


def test_graph_context_none_when_no_graph(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        gc = gc_svc.build_graph_context(
            db, project_id=pid, graph_version_id=None,
        )
    assert gc is None


def test_graph_context_version_stable():
    assert gc_svc.GRAPH_CONTEXT_VERSION == "m26-graph-ctx-v1"


def test_load_gap_source_ids_empty_when_no_gap_nodes(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    from app.db.models.knowledge_graph import KnowledgeGraphVersion
    from app.domain.knowledge_graph import KNOWLEDGE_GRAPH_VERSION

    with SessionLocal() as db:
        gv = KnowledgeGraphVersion(
            project_id=pid,
            version=1,
            status="ready",
            graph_version=KNOWLEDGE_GRAPH_VERSION,
            context_hash=f"t-{uuid.uuid4().hex[:8]}",
        )
        db.add(gv)
        db.commit()
        gv_id = gv.id

    with SessionLocal() as db:
        ids = gc_svc.load_gap_source_ids(
            db, project_id=pid, graph_version_id=gv_id,
        )
    assert ids == set()
