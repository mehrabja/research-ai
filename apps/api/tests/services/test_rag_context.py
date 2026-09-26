"""M26 — P1 Stage A context tests (final)."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.exceptions import RetrievalAdvancedInvalid
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.research_plan import (
    ResearchPlan,
    ResearchPlanSection,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.embeddings import EmbeddingProfile
from app.services import projects as projects_service
from app.services.rag import context as ctx_svc
from app.services.rag import orchestrator as orch
from app.services.rag.jobs import AdvancedRAGJobPayload


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
            email=f"rag-ctx-{uid.hex[:8]}@e.com",
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


def _profile_alt() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="openai",
        model="text-embedding-3-large",
        dimensions=1536,
        distance_metric="cosine",
        profile_version="m9.2",
    )


def _mk_plan_with_section(project_id, *, version=1):
    with SessionLocal() as db:
        plan = ResearchPlan(
            project_id=project_id,
            version=version,
            status="ready",
            planner_version="m24.1",
            planning_mode="deterministic",
            context_hash=f"ctx-{uuid.uuid4().hex[:8]}",
        )
        db.add(plan)
        db.flush()
        section = ResearchPlanSection(
            plan_id=plan.id,
            section_key=f"sec-{uuid.uuid4().hex[:6]}",
            title="Section",
            section_type="narrative",
            display_order=0,
            required=True,
            word_budget=100,
            budget_weight=0,
            evidence_coverage_target=0,
            status="active",
        )
        db.add(section)
        db.commit()
        return plan.id, section.id


def _isolate_pipeline(monkeypatch) -> None:
    """Make the orchestrator pipeline a no-op so context reuse is
    the only thing under test."""
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


# ---------- deterministic ----------


def test_resolve_context_deterministic(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        c1 = ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid,
            query="hello world",
            provider=_provider(), profile=_profile(),
            mode="lexical",
        )
        c2 = ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid,
            query="hello world",
            provider=_provider(), profile=_profile(),
            mode="lexical",
        )
    assert c1.context_hash == c2.context_hash


# ---------- ownership ----------


def test_resolve_context_rejects_cross_project_section(cleanup_users):
    u1 = _mk_user(cleanup_users)
    u2 = _mk_user(cleanup_users)
    pid = _mk_project(u1)
    other_pid = _mk_project(u2)
    _, foreign_section_id = _mk_plan_with_section(other_pid)

    with SessionLocal() as db, pytest.raises(RetrievalAdvancedInvalid):
        ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=u1, query="x",
            provider=_provider(), profile=_profile(),
            plan_section_id=foreign_section_id,
        )


def test_resolve_context_rejects_foreign_report(cleanup_users):
    u1 = _mk_user(cleanup_users)
    u2 = _mk_user(cleanup_users)
    pid = _mk_project(u1)
    other_pid = _mk_project(u2)

    with SessionLocal() as db:
        r = Report(
            user_id=u2, project_id=other_pid, topic="t",
            output_language="en", status="draft",
        )
        db.add(r)
        db.commit()
        foreign_report_id = r.id

    with SessionLocal() as db, pytest.raises(RetrievalAdvancedInvalid):
        ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=u1, query="x",
            provider=_provider(), profile=_profile(),
            report_id=foreign_report_id,
        )


# ---------- request validation ----------


def test_resolve_context_rejects_max_results_zero(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db, pytest.raises(RetrievalAdvancedInvalid):
        ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            max_results=0,
        )


def test_resolve_context_rejects_inverted_year_range(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db, pytest.raises(RetrievalAdvancedInvalid):
        ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            min_year=2020, max_year=2010,
        )


def test_resolve_context_rejects_invalid_mode(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db, pytest.raises(RetrievalAdvancedInvalid):
        ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            mode="bogus",  # type: ignore[arg-type]
        )


def test_resolve_context_rejects_invalid_algorithm(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db, pytest.raises(RetrievalAdvancedInvalid):
        ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            algorithm="bogus",  # type: ignore[arg-type]
        )


def test_resolve_context_normalizes_allowed_source_ids(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    with SessionLocal() as db:
        c1 = ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            allowed_source_ids=[s1, s2, s1],
        )
    assert c1.filters.allowed_source_ids == tuple(
        sorted({s1, s2}, key=str)
    )


# ---------- lock key ----------


def test_resolve_context_lock_key_deterministic():
    pid = uuid.uuid4()
    k1 = ctx_svc.compute_context_lock_key(
        project_id=pid, context_hash="abc"
    )
    k2 = ctx_svc.compute_context_lock_key(
        project_id=pid, context_hash="abc"
    )
    k3 = ctx_svc.compute_context_lock_key(
        project_id=pid, context_hash="xyz"
    )
    k4 = ctx_svc.compute_context_lock_key(
        project_id=uuid.uuid4(), context_hash="abc"
    )
    assert k1 == k2
    assert k1 != k3
    assert k1 != k4
    assert -(2**63) <= k1 < 2**63


# ---------- sync context reuse ----------


def test_sync_orchestrator_reuses_provided_context(
    cleanup_users, monkeypatch
):
    _isolate_pipeline(monkeypatch)
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        ctx = ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid, query="hello world",
            provider=_provider(), profile=_profile(),
            mode="lexical", algorithm="ann",
        )

    call_count = {"n": 0}
    real = ctx_svc.resolve_retrieval_context

    def _counting(*a, **k):
        call_count["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(
        orch.ctx_svc, "resolve_retrieval_context", _counting
    )

    with SessionLocal() as db:
        outcome = orch.retrieve_research_context(
            db,
            request=orch.RetrievalRequest(
                project_id=pid, user_id=uid, query="hello world",
                provider=_provider(), profile=_profile(),
                mode="lexical", algorithm="ann",
            ),
            context=ctx,
        )

    assert call_count["n"] == 0
    assert outcome.run.context_hash == ctx.context_hash
    assert outcome.run.project_id == ctx.project_id


def test_sync_orchestrator_resolves_when_no_context(
    cleanup_users, monkeypatch
):
    _isolate_pipeline(monkeypatch)
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    call_count = {"n": 0}
    real = ctx_svc.resolve_retrieval_context

    def _counting(*a, **k):
        call_count["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(
        orch.ctx_svc, "resolve_retrieval_context", _counting
    )

    with SessionLocal() as db:
        orch.retrieve_research_context(
            db,
            request=orch.RetrievalRequest(
                project_id=pid, user_id=uid, query="hello world",
                provider=_provider(), profile=_profile(),
                mode="lexical", algorithm="ann",
            ),
        )
    assert call_count["n"] == 1


# ---------- context/request mismatch ----------


def _request_for(ctx, **overrides):
    base = {
        "project_id": ctx.project_id,
        "user_id": ctx.user_id,
        "query": ctx.query,
        "provider": ctx.provider,
        "profile": ctx.profile,
        "report_id": ctx.report_id,
        "plan_section_id": (
            ctx.section.id if ctx.section else None
        ),
        "evidence_requirement_id": (
            ctx.requirement.id if ctx.requirement else None
        ),
        "mode": ctx.mode,
        "algorithm": ctx.algorithm,
        "max_results": ctx.config.max_results,
        "graph_expansion_enabled": ctx.config.graph_enabled,
        "memory_enabled": ctx.config.memory_enabled,
        "diversity_enabled": ctx.config.diversity_enabled,
        "min_year": ctx.filters.min_year,
        "max_year": ctx.filters.max_year,
        "required_full_text": ctx.filters.required_full_text,
        "allowed_source_ids": (
            list(ctx.filters.allowed_source_ids) or None
        ),
    }
    base.update(overrides)
    return orch.RetrievalRequest(**base)


def test_context_request_mismatch_project(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    other_pid = _mk_project(uid)
    with SessionLocal() as db:
        ctx = ctx_svc.resolve_retrieval_context(
            db, project_id=other_pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
        )
        req = _request_for(ctx, project_id=pid)
        with pytest.raises(RetrievalAdvancedInvalid):
            orch.retrieve_research_context(
                db, request=req, context=ctx
            )


def test_context_request_mismatch_query(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        ctx = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="alpha",
            provider=_provider(), profile=_profile(),
        )
        req = _request_for(ctx, query="beta")
        with pytest.raises(RetrievalAdvancedInvalid):
            orch.retrieve_research_context(
                db, request=req, context=ctx
            )


def test_context_request_mismatch_mode(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        ctx = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            mode="lexical",
        )
        req = _request_for(ctx, mode="hybrid")
        with pytest.raises(RetrievalAdvancedInvalid):
            orch.retrieve_research_context(
                db, request=req, context=ctx
            )


def test_context_request_mismatch_profile(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        ctx = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
        )
        req = _request_for(ctx, profile=_profile_alt())
        with pytest.raises(RetrievalAdvancedInvalid):
            orch.retrieve_research_context(
                db, request=req, context=ctx
            )


def test_context_request_max_results_capped_match(cleanup_users):
    """Request above cap → effective capped → consistency guard accepts.

    Directly exercises the guard. Does NOT run the retrieval pipeline.
    """
    settings = get_settings()
    cap = settings.rag_max_results
    top_k_cap = settings.embedding_retrieval_top_k_max
    effective_cap = min(cap, top_k_cap)

    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        ctx = ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            max_results=cap + 1000,
        )
    assert ctx.config.max_results == effective_cap

    req = _request_for(ctx, max_results=cap + 1000)
    # Guard is the only thing under test — no retrieval pipeline.
    orch._validate_context_matches_request(request=req, context=ctx)


# ---------- worker stale-context + success path ----------


def _payload_dict(
    *, project_id, user_id, query, context_hash,
    mode="lexical", algorithm="ann",
):
    return {
        "project_id": str(project_id),
        "user_id": str(user_id),
        "query": query,
        "context_hash": context_hash,
        "mode": mode,
        "algorithm": algorithm,
    }


def test_worker_rejects_stale_context(
    cleanup_users, monkeypatch
):
    from app.workers import rag_handlers

    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        known_ctx = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="hello world",
            provider=_provider(), profile=_profile(),
        )

    monkeypatch.setattr(
        rag_handlers, "get_current_embedding_profile",
        lambda: _profile(),
    )
    monkeypatch.setattr(
        rag_handlers, "build_embedding_provider",
        lambda profile: _provider(),
    )
    monkeypatch.setattr(
        rag_handlers.ctx_svc, "resolve_retrieval_context",
        lambda *a, **k: known_ctx,
    )

    called = {"value": False}

    def _must_not_run(*a, **k):
        called["value"] = True
        raise AssertionError("orchestrator must not execute")

    monkeypatch.setattr(
        rag_handlers, "retrieve_research_context", _must_not_run
    )

    job_ctx = type("Ctx", (), {})()
    job_ctx.payload = _payload_dict(
        project_id=pid, user_id=uid, query="hello world",
        context_hash="deadbeef" * 4,
    )

    with pytest.raises(RetrievalAdvancedInvalid):
        rag_handlers.handle_advanced_rag_retrieve(job_ctx)
    assert called["value"] is False


def test_worker_success_reuses_resolved_context(
    cleanup_users, monkeypatch
):
    from app.workers import rag_handlers

    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        known_ctx = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="hello world",
            provider=_provider(), profile=_profile(),
        )

    monkeypatch.setattr(
        rag_handlers, "get_current_embedding_profile",
        lambda: _profile(),
    )
    monkeypatch.setattr(
        rag_handlers, "build_embedding_provider",
        lambda profile: _provider(),
    )
    monkeypatch.setattr(
        rag_handlers.ctx_svc, "resolve_retrieval_context",
        lambda *a, **k: known_ctx,
    )

    captured = {"ctx": None}

    class _FakeRun:
        status = "completed"
        id = uuid.uuid4()

    class _FakeOutcome:
        run = _FakeRun()
        cached = False
        results: list = []

    def _capture(db, *, request, context):
        captured["ctx"] = context
        return _FakeOutcome()

    monkeypatch.setattr(
        rag_handlers, "retrieve_research_context", _capture
    )

    job_ctx = type("Ctx", (), {})()
    job_ctx.payload = _payload_dict(
        project_id=pid, user_id=uid, query="hello world",
        context_hash=known_ctx.context_hash,
    )

    out = rag_handlers.handle_advanced_rag_retrieve(job_ctx)
    assert captured["ctx"] is known_ctx
    assert out["status"] == "completed"


# ---------- payload schema ----------


def test_job_payload_rejects_invalid_uuid():
    with pytest.raises(ValidationError):
        AdvancedRAGJobPayload(
            project_id="not-a-uuid",
            user_id=uuid.uuid4(),
            query="x", context_hash="abc",
            mode="lexical", algorithm="ann",
        )


def test_job_payload_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        AdvancedRAGJobPayload(
            project_id=uuid.uuid4(), user_id=uuid.uuid4(),
            query="x", context_hash="abc",
            mode="bogus", algorithm="ann",  # type: ignore[arg-type]
        )


def test_job_payload_rejects_negative_max_results():
    with pytest.raises(ValidationError):
        AdvancedRAGJobPayload(
            project_id=uuid.uuid4(), user_id=uuid.uuid4(),
            query="x", context_hash="abc",
            mode="lexical", algorithm="ann", max_results=-1,
        )


def test_job_payload_rejects_zero_max_results():
    with pytest.raises(ValidationError):
        AdvancedRAGJobPayload(
            project_id=uuid.uuid4(), user_id=uuid.uuid4(),
            query="x", context_hash="abc",
            mode="lexical", algorithm="ann", max_results=0,
        )


def test_job_payload_rejects_empty_query():
    with pytest.raises(ValidationError):
        AdvancedRAGJobPayload(
            project_id=uuid.uuid4(), user_id=uuid.uuid4(),
            query="", context_hash="abc",
            mode="lexical", algorithm="ann",
        )


def test_job_payload_rejects_empty_context_hash():
    with pytest.raises(ValidationError):
        AdvancedRAGJobPayload(
            project_id=uuid.uuid4(), user_id=uuid.uuid4(),
            query="x", context_hash="",
            mode="lexical", algorithm="ann",
        )


def test_job_payload_rejects_invalid_allowed_source_id():
    with pytest.raises(ValidationError):
        AdvancedRAGJobPayload(
            project_id=uuid.uuid4(), user_id=uuid.uuid4(),
            query="x", context_hash="abc",
            mode="lexical", algorithm="ann",
            allowed_source_ids=["not-a-uuid"],
        )


def test_job_payload_rejects_inverted_year_range():
    with pytest.raises(ValidationError):
        AdvancedRAGJobPayload(
            project_id=uuid.uuid4(), user_id=uuid.uuid4(),
            query="x", context_hash="abc",
            mode="lexical", algorithm="ann",
            min_year=2025, max_year=2010,
        )


def test_job_payload_accepts_max_results_above_settings_cap():
    """Payload validation is basic; runtime caps in resolution."""
    payload = AdvancedRAGJobPayload(
        project_id=uuid.uuid4(), user_id=uuid.uuid4(),
        query="x", context_hash="abc",
        mode="lexical", algorithm="ann", max_results=999,
    )
    assert payload.max_results == 999


# ---------- sync/async hash parity ----------


def test_sync_async_hash_parity(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)

    with SessionLocal() as db:
        sync_ctx = ctx_svc.resolve_retrieval_context(
            db,
            project_id=pid, user_id=uid, query="hello world",
            provider=_provider(), profile=_profile(),
            mode="lexical", algorithm="ann",
        )

    payload = AdvancedRAGJobPayload(
        project_id=pid, user_id=uid, query="hello world",
        context_hash=sync_ctx.context_hash,
        mode=sync_ctx.mode, algorithm=sync_ctx.algorithm,
        max_results=sync_ctx.config.max_results,
        graph_expansion_enabled=sync_ctx.config.graph_enabled,
        memory_enabled=sync_ctx.config.memory_enabled,
        diversity_enabled=sync_ctx.config.diversity_enabled,
        min_year=sync_ctx.filters.min_year,
        max_year=sync_ctx.filters.max_year,
        required_full_text=sync_ctx.filters.required_full_text,
        allowed_source_ids=(
            list(sync_ctx.filters.allowed_source_ids) or None
        ),
    )

    with SessionLocal() as db:
        worker_ctx = ctx_svc.resolve_retrieval_context(
            db,
            project_id=payload.project_id,
            user_id=payload.user_id,
            query=payload.query,
            provider=_provider(), profile=_profile(),
            mode=payload.mode, algorithm=payload.algorithm,
            max_results=payload.max_results,
            graph_expansion_enabled=payload.graph_expansion_enabled,
            memory_enabled=payload.memory_enabled,
            diversity_enabled=payload.diversity_enabled,
            min_year=payload.min_year,
            max_year=payload.max_year,
            required_full_text=payload.required_full_text,
            allowed_source_ids=payload.allowed_source_ids,
        )
    assert sync_ctx.context_hash == worker_ctx.context_hash


def test_different_allowed_source_ids_change_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    with SessionLocal() as db:
        h1 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            allowed_source_ids=[s1],
        ).context_hash
        h2 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            allowed_source_ids=[s2],
        ).context_hash
    assert h1 != h2


def test_different_max_results_change_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h1 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            max_results=10,
        ).context_hash
        h2 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            max_results=20,
        ).context_hash
    assert h1 != h2


def test_different_graph_flag_changes_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        h1 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            graph_expansion_enabled=False,
        ).context_hash
        h2 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            graph_expansion_enabled=True,
        ).context_hash
    assert h1 != h2


def test_different_report_id_changes_hash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    with SessionLocal() as db:
        r1 = Report(
            user_id=uid, project_id=pid, topic="t1",
            output_language="en", status="draft",
        )
        r2 = Report(
            user_id=uid, project_id=pid, topic="t2",
            output_language="en", status="draft",
        )
        db.add_all([r1, r2])
        db.commit()
        r1_id, r2_id = r1.id, r2.id

    with SessionLocal() as db:
        h1 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            report_id=r1_id,
        ).context_hash
        h2 = ctx_svc.resolve_retrieval_context(
            db, project_id=pid, user_id=uid, query="x",
            provider=_provider(), profile=_profile(),
            report_id=r2_id,
        ).context_hash
    assert h1 != h2
