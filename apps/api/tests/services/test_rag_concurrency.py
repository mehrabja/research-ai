"""M26 — Real concurrency test for retrieval cache.

Two independent sessions attempt the same context concurrently.
Exactly one RetrievalRun must be persisted; the second caller must
observe a cache hit.

Uses threading.Barrier for deterministic synchronization. No sleeps.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.db.models.project import Project, ProjectEvent
from app.db.models.retrieval import RetrievalRun
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.embeddings import EmbeddingProfile
from app.services import projects as projects_service
from app.services.rag import context as ctx_svc
from app.services.rag import orchestrator as orch


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
            id=uid, email=f"rag-cc-{uid.hex[:8]}@e.com",
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


def test_concurrent_same_context_produces_one_run(
    cleanup_users, monkeypatch
):
    _isolate_pipeline(monkeypatch)
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        ctx = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            mode="lexical",
        )

    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def _worker():
        try:
            with SessionLocal() as db:
                barrier.wait(timeout=10)
                out = orch.retrieve_research_context(
                    db,
                    request=orch.RetrievalRequest(
                        project_id=pid, user_id=uid, query="x",
                        provider=_provider(), profile=_profile(),
                        mode="lexical",
                    ),
                    context=ctx,
                )
                results.append(out)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    t1.join(timeout=20)
    t2.join(timeout=20)

    assert errors == [], f"workers raised: {errors}"
    assert len(results) == 2

    with SessionLocal() as db:
        count = db.execute(
            select(func.count()).select_from(RetrievalRun).where(
                RetrievalRun.project_id == pid,
                RetrievalRun.status == "completed",
            )
        ).scalar_one()
    assert count == 1

    cached_flags = sorted(r.cached for r in results)
    assert cached_flags == [False, True]
