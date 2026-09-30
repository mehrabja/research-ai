"""M26 — Orchestrator: main retrieval entrypoint.

Pipeline:
    resolve context
    → advisory-lock cache check (double-check)
    → optional LLM decomposition
    → M09/M11 candidate generation (per subquery, merged)
    → M25 graph expansion
    → M24 requirement filter
    → deterministic scoring
    → optional LLM rerank
    → MMR / diversity
    → real intent coverage (with M25 graph context)
    → persist run
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    RetrievalAdvancedConfigurationInvalid,
    RetrievalAdvancedInvalid,
)
from app.db.models.literature import ProjectLiteratureItem
from app.db.models.retrieval import RetrievalResult, RetrievalRun
from app.db.models.source import Chunk, Source
from app.domain.embeddings import (
    EmbeddingProfile,
    build_embedding_profile_id,
)
from app.domain.retrieval import RetrievalAlgorithm, RetrievalMode
from app.domain.retrieval_advanced import (
    ADVANCED_RAG_VERSION,
    RANKING_MODEL_VERSION,
    RetrievalRunStatus,
)
from app.integrations.embeddings.base import EmbeddingProvider
from app.integrations.generation.base import GenerationProvider
from app.services.evidence_contract import from_chunk
from app.services.generation_profile import build_generation_provider
from app.services.projects import get_project
from app.services.rag import candidates as cand_svc
from app.services.rag import context as ctx_svc
from app.services.rag import coverage as cov_svc
from app.services.rag import decomposition as dec_svc
from app.services.rag import diversity as div_svc
from app.services.rag import graph_context as gc_svc
from app.services.rag import graph_expansion as gx_svc
from app.services.rag import llm_decomposition as llm_dec_svc
from app.services.rag import llm_rerank as llm_rerank_svc
from app.services.rag import memory as mem_svc
from app.services.rag import normalization as norm_svc
from app.services.rag import plan_filter as plan_svc
from app.services.rag import scoring as score_svc
from app.services.rag.context import (
    ResolvedRetrievalContext,
    effective_max_results,
)

logger = logging.getLogger(__name__)


@dataclass
class RetrievalRequest:
    project_id: uuid.UUID
    user_id: uuid.UUID
    query: str
    provider: EmbeddingProvider
    profile: EmbeddingProfile
    report_id: uuid.UUID | None = None
    plan_section_id: uuid.UUID | None = None
    evidence_requirement_id: uuid.UUID | None = None
    mode: RetrievalMode = "lexical"
    algorithm: RetrievalAlgorithm = "ann"
    max_results: int | None = None
    graph_expansion_enabled: bool | None = None
    memory_enabled: bool | None = None
    diversity_enabled: bool | None = None
    min_year: int | None = None
    max_year: int | None = None
    required_full_text: bool = False
    allowed_source_ids: list[uuid.UUID] | None = None
    generation_provider: GenerationProvider | None = None


@dataclass
class RetrievalOutcome:
    run: RetrievalRun
    results: list[dict] = field(default_factory=list)
    coverage: dict | None = None
    warnings: list[str] = field(default_factory=list)
    cached: bool = False


def _load_sources(
    db: Session, *, source_ids: set[uuid.UUID]
) -> dict[uuid.UUID, Source]:
    if not source_ids:
        return {}
    rows = db.execute(
        select(Source).where(Source.id.in_(list(source_ids)))
    ).scalars().all()
    return {s.id: s for s in rows}


def _load_literature_items(
    db: Session,
    *,
    project_id: uuid.UUID,
    source_ids: set[uuid.UUID],
) -> dict[uuid.UUID, ProjectLiteratureItem]:
    if not source_ids:
        return {}
    rows = db.execute(
        select(ProjectLiteratureItem).where(
            ProjectLiteratureItem.project_id == project_id,
            ProjectLiteratureItem.source_id.in_(list(source_ids)),
        )
    ).scalars().all()
    return {row.source_id: row for row in rows}


def _load_chunk_snippets(
    db: Session, *, chunk_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not chunk_ids:
        return {}
    rows = db.execute(
        select(Chunk.id, Chunk.content).where(
            Chunk.id.in_(list(chunk_ids))
        )
    ).tuples().all()
    return dict(rows)


def _now(db: Session):
    return db.execute(text("SELECT now()")).scalar()


def _acquire_context_lock(
    db: Session,
    *,
    project_id: uuid.UUID,
    context_hash: str,
) -> None:
    key = ctx_svc.compute_context_lock_key(
        project_id=project_id, context_hash=context_hash
    )
    db.execute(
        text("SELECT pg_advisory_xact_lock(:k)"), {"k": key}
    )


def _validate_context_matches_request(
    *,
    request: RetrievalRequest,
    context: ResolvedRetrievalContext,
) -> None:
    if context.project_id != request.project_id:
        raise RetrievalAdvancedInvalid("context/project mismatch")
    if context.user_id != request.user_id:
        raise RetrievalAdvancedInvalid("context/user mismatch")
    if context.report_id != request.report_id:
        raise RetrievalAdvancedInvalid("context/report mismatch")

    if context.mode != request.mode:
        raise RetrievalAdvancedInvalid("context/mode mismatch")
    if context.algorithm != request.algorithm:
        raise RetrievalAdvancedInvalid("context/algorithm mismatch")

    normalized, qhash = norm_svc.normalize_and_hash(request.query)
    if normalized != context.normalized_query:
        raise RetrievalAdvancedInvalid("context/query mismatch")
    if qhash != context.query_hash:
        raise RetrievalAdvancedInvalid("context/query-hash mismatch")

    request_profile_id = build_embedding_profile_id(request.profile)
    if request_profile_id != context.profile_id:
        raise RetrievalAdvancedInvalid("context/profile mismatch")

    request_section_id = request.plan_section_id
    context_section_id = (
        context.section.id if context.section else None
    )
    if request_section_id != context_section_id:
        raise RetrievalAdvancedInvalid(
            "context/plan-section mismatch"
        )

    request_requirement_id = request.evidence_requirement_id
    context_requirement_id = (
        context.requirement.id if context.requirement else None
    )
    if request_requirement_id != context_requirement_id:
        raise RetrievalAdvancedInvalid(
            "context/evidence-requirement mismatch"
        )

    if request.min_year != context.filters.min_year:
        raise RetrievalAdvancedInvalid("context/min-year mismatch")
    if request.max_year != context.filters.max_year:
        raise RetrievalAdvancedInvalid("context/max-year mismatch")
    if (
        request.required_full_text
        != context.filters.required_full_text
    ):
        raise RetrievalAdvancedInvalid(
            "context/required-full-text mismatch"
        )

    request_sources = tuple(
        sorted(set(request.allowed_source_ids or []), key=str)
    )
    if request_sources != context.filters.allowed_source_ids:
        raise RetrievalAdvancedInvalid(
            "context/allowed-source-ids mismatch"
        )

    if (
        request.graph_expansion_enabled is not None
        and request.graph_expansion_enabled
        != context.config.graph_enabled
    ):
        raise RetrievalAdvancedInvalid("context/graph-flag mismatch")
    if (
        request.memory_enabled is not None
        and request.memory_enabled != context.config.memory_enabled
    ):
        raise RetrievalAdvancedInvalid("context/memory-flag mismatch")
    if (
        request.diversity_enabled is not None
        and request.diversity_enabled
        != context.config.diversity_enabled
    ):
        raise RetrievalAdvancedInvalid(
            "context/diversity-flag mismatch"
        )

    settings = get_settings()
    request_effective_max = effective_max_results(
        request_max=request.max_results,
        settings=settings,
    )
    if request_effective_max != context.config.max_results:
        raise RetrievalAdvancedInvalid(
            "context/max-results mismatch"
        )


def _lookup_cached_run(
    db: Session,
    *,
    project_id: uuid.UUID,
    context_hash: str,
) -> tuple[RetrievalRun | None, list[RetrievalResult]]:
    run = db.execute(
        select(RetrievalRun).where(
            RetrievalRun.project_id == project_id,
            RetrievalRun.context_hash == context_hash,
            RetrievalRun.status == RetrievalRunStatus.COMPLETED.value,
        )
    ).scalar_one_or_none()
    if run is None:
        return None, []
    rows = list(db.execute(
        select(RetrievalResult)
        .where(RetrievalResult.retrieval_run_id == run.id)
        .order_by(RetrievalResult.rank.asc())
    ).scalars().all())
    return run, rows


def retrieve_research_context(
    db: Session,
    *,
    request: RetrievalRequest,
    context: ResolvedRetrievalContext | None = None,
    generation_provider: GenerationProvider | None = None,
) -> RetrievalOutcome:
    settings = get_settings()
    if not settings.rag_enabled:
        raise RetrievalAdvancedConfigurationInvalid(
            "advanced rag is disabled"
        )

    get_project(
        db, user_id=request.user_id, project_id=request.project_id
    )

    if context is not None:
        _validate_context_matches_request(
            request=request, context=context
        )
        ctx = context
    else:
        ctx = ctx_svc.resolve_retrieval_context(
            db,
            project_id=request.project_id,
            user_id=request.user_id,
            query=request.query,
            provider=request.provider,
            profile=request.profile,
            report_id=request.report_id,
            plan_section_id=request.plan_section_id,
            evidence_requirement_id=request.evidence_requirement_id,
            mode=request.mode,
            algorithm=request.algorithm,
            max_results=request.max_results,
            graph_expansion_enabled=request.graph_expansion_enabled,
            memory_enabled=request.memory_enabled,
            diversity_enabled=request.diversity_enabled,
            min_year=request.min_year,
            max_year=request.max_year,
            required_full_text=request.required_full_text,
            allowed_source_ids=request.allowed_source_ids,
        )

    # ---- Fast-path cache lookup ----
    cached_run, cached_rows = _lookup_cached_run(
        db,
        project_id=ctx.project_id,
        context_hash=ctx.context_hash,
    )
    if cached_run is not None:
        return RetrievalOutcome(
            run=cached_run,
            results=[_result_to_dict(r) for r in cached_rows],
            coverage=cached_run.coverage,
            warnings=list(cached_run.warnings or []),
            cached=True,
        )

    # ---- Advisory lock, then re-check ----
    _acquire_context_lock(
        db,
        project_id=ctx.project_id,
        context_hash=ctx.context_hash,
    )
    cached_run, cached_rows = _lookup_cached_run(
        db,
        project_id=ctx.project_id,
        context_hash=ctx.context_hash,
    )
    if cached_run is not None:
        return RetrievalOutcome(
            run=cached_run,
            results=[_result_to_dict(r) for r in cached_rows],
            coverage=cached_run.coverage,
            warnings=list(cached_run.warnings or []),
            cached=True,
        )

    started = time.perf_counter()
    run = RetrievalRun(
        project_id=ctx.project_id,
        user_id=ctx.user_id,
        report_id=ctx.report_id,
        research_plan_id=ctx.plan.id if ctx.plan else None,
        plan_section_id=ctx.section.id if ctx.section else None,
        evidence_requirement_id=(
            ctx.requirement.id if ctx.requirement else None
        ),
        graph_version_id=ctx.graph_version_id,
        query=ctx.query,
        normalized_query=ctx.normalized_query,
        query_hash=ctx.query_hash,
        context_hash=ctx.context_hash,
        retrieval_version=ADVANCED_RAG_VERSION,
        ranking_model_version=RANKING_MODEL_VERSION,
        status=RetrievalRunStatus.RUNNING.value,
    )
    db.add(run)
    db.flush()

    warnings: list[str] = []
    decomposition_used = False
    decomposition_fallback = False
    rerank_used = False
    rerank_fallback = False
    graph_context: dict | None = None

    try:
        decomposition = dec_svc.decompose_deterministic(
            ctx.normalized_query
        )
        requested_intents = [d.intent for d in decomposition]

        # ---- Optional LLM provider ----
        llm_provider: GenerationProvider | None = None
        if (
            settings.rag_llm_decomposition_enabled
            or settings.rag_llm_rerank_enabled
        ):
            llm_provider = (
                generation_provider
                or request.generation_provider
                or build_generation_provider()
            )

        # ---- Optional LLM decomposition ----
        subqueries: list[str] = [ctx.normalized_query]
        if (
            settings.rag_llm_decomposition_enabled
            and llm_provider is not None
        ):
            subqueries, dec_warnings = llm_dec_svc.decompose_query(
                normalized_query=ctx.normalized_query,
                provider=llm_provider,
            )
            decomposition_used = True
            if "llm_decomposition_fallback" in dec_warnings:
                decomposition_fallback = True
                warnings.extend(dec_warnings)

        allowed_source_ids = (
            list(ctx.filters.allowed_source_ids)
            if ctx.filters.allowed_source_ids
            else None
        )

        # ---- Candidate generation per subquery, merged ----
        merged: dict[uuid.UUID, cand_svc.Candidate] = {}
        for sq in subqueries:
            raw_part, _cov, warnings_cand = cand_svc.generate_candidates(
                db,
                user_id=ctx.user_id,
                project_id=ctx.project_id,
                query=sq,
                mode=ctx.mode,
                algorithm=ctx.algorithm,
                limit=ctx.config.candidate_limit,
                allowed_source_ids=allowed_source_ids,
                provider=ctx.provider,
                profile=ctx.profile,
            )
            warnings.extend(warnings_cand)
            for c in raw_part:
                prev = merged.get(c.chunk_id)
                if prev is None or c.fusion_score > prev.fusion_score:
                    merged[c.chunk_id] = c

        raw = sorted(
            merged.values(),
            key=lambda c: (-c.fusion_score, str(c.chunk_id)),
        )[: ctx.config.candidate_limit]

        if not raw:
            warnings.append("no_candidates")

        # ---- Graph expansion ----
        if (
            ctx.config.graph_enabled
            and ctx.graph_version_id is not None
            and raw
        ):
            raw, gw = gx_svc.expand_candidates(
                db,
                project_id=ctx.project_id,
                graph_version_id=ctx.graph_version_id,
                seed_candidates=raw,
                max_depth=settings.rag_max_graph_depth,
                max_nodes=settings.rag_max_graph_nodes,
            )
            warnings.extend(gw)

        # ---- Graph context for coverage ----
        graph_context = gc_svc.build_graph_context(
            db,
            project_id=ctx.project_id,
            graph_version_id=ctx.graph_version_id,
        )

        # ---- Metadata ----
        source_ids = {c.source_id for c in raw}
        sources_by_id = _load_sources(db, source_ids=source_ids)
        literature_by_source_id = _load_literature_items(
            db,
            project_id=ctx.project_id,
            source_ids=source_ids,
        )

        # ---- User filters + requirement filter ----
        raw, filter_warnings = plan_svc.apply_plan_filters(
            raw,
            min_year=ctx.filters.min_year,
            max_year=ctx.filters.max_year,
            required_full_text=ctx.filters.required_full_text,
            sources_by_id=sources_by_id,
        )
        warnings.extend(filter_warnings)

        requirement_filter_meta: dict | None = None
        if ctx.requirement is not None:
            filter_result = plan_svc.apply_requirement_filter(
                raw,
                requirement=ctx.requirement,
                sources_by_id=sources_by_id,
                literature_by_source_id=literature_by_source_id,
            )
            raw = filter_result.candidates
            warnings.extend(filter_result.warnings)
            requirement_filter_meta = {
                "rejected_counts": filter_result.rejected_counts,
                "distinct_source_count": (
                    filter_result.distinct_source_count
                ),
                "min_sources_satisfied": (
                    filter_result.min_sources_satisfied
                ),
            }

        # ---- Deterministic scoring ----
        scored = score_svc.score_candidates(
            raw, sources_by_id=sources_by_id
        )

        # ---- Optional LLM rerank ----
        if (
            settings.rag_llm_rerank_enabled
            and llm_provider is not None
            and scored
        ):
            bounded = scored[: llm_rerank_svc.MAX_RERANK_CANDIDATES]
            chunk_ids = {s.candidate.chunk_id for s in bounded}
            snippets = _load_chunk_snippets(db, chunk_ids=chunk_ids)
            input_items = [
                {
                    "chunk_id": str(s.candidate.chunk_id),
                    "score": float(s.final_score),
                    "snippet": snippets.get(s.candidate.chunk_id, ""),
                }
                for s in bounded
            ]
            reordered_candidates, rerank_warnings = (
                llm_rerank_svc.rerank_candidates(
                    normalized_query=ctx.normalized_query,
                    candidates=input_items,
                    provider=llm_provider,
                )
            )
            rerank_used = True
            if "llm_rerank_fallback" in rerank_warnings:
                rerank_fallback = True
                warnings.extend(rerank_warnings)

            by_id = {s.candidate.chunk_id: s for s in scored}
            new_order: list = []
            for item in reordered_candidates:
                try:
                    cid = uuid.UUID(item["chunk_id"])
                except (ValueError, TypeError, KeyError):
                    continue
                sc = by_id.get(cid)
                if sc is not None:
                    new_order.append(sc)
            if len(new_order) == len(scored):
                scored = new_order

        # ---- Memory hints ----
        if ctx.config.memory_enabled:
            try:
                _apply_memory_hints(
                    db,
                    project_id=ctx.project_id,
                    scored=scored,
                )
            except Exception:
                logger.exception("rag_memory_hint_failed")
                warnings.append("memory_hint_failed")

        # ---- MMR / diversity ----
        if ctx.config.diversity_enabled:
            final = div_svc.apply_mmr(
                scored,
                lambda_=settings.rag_mmr_lambda,
                max_results=ctx.config.max_results,
            )
        else:
            final = scored[: ctx.config.max_results]

        # ---- Persist results ----
        result_dicts: list[dict] = []
        final_chunk_ids = {sc.candidate.chunk_id for sc in final}
        final_chunks = {
            chunk.id: chunk
            for chunk in db.execute(
                select(Chunk).where(Chunk.id.in_(final_chunk_ids))
            ).scalars().all()
        }
        for rank, sc in enumerate(final, start=1):
            chunk = final_chunks.get(sc.candidate.chunk_id)
            evidence = from_chunk(chunk) if chunk is not None else None
            result_meta = (
                {
                    "evidence_key": evidence.evidence_key,
                    "project_file_id": (
                        str(evidence.project_file_id)
                        if evidence.project_file_id is not None
                        else None
                    ),
                }
                if evidence is not None
                else None
            )
            rr = RetrievalResult(
                retrieval_run_id=run.id,
                project_id=ctx.project_id,
                chunk_id=sc.candidate.chunk_id,
                source_id=sc.candidate.source_id,
                rank=rank,
                vector_score=sc.vector_score,
                lexical_score=sc.lexical_score,
                graph_score=sc.graph_score,
                memory_score=sc.memory_score,
                quality_score=sc.quality_score,
                diversity_penalty=sc.diversity_penalty,
                final_score=sc.final_score,
                retrieval_stage=sc.candidate.stage,
                retrieval_reason=list(sc.reasons),
                graph_distance=sc.graph_distance,
                memory_match=None,
                result_meta=result_meta,
            )
            db.add(rr)
            result_dicts.append({
                "rank": rank,
                "chunk_id": sc.candidate.chunk_id,
                "source_id": sc.candidate.source_id,
                "final_score": sc.final_score,
                "vector_score": sc.vector_score,
                "lexical_score": sc.lexical_score,
                "graph_score": sc.graph_score,
                "memory_score": sc.memory_score,
                "quality_score": sc.quality_score,
                "diversity_penalty": sc.diversity_penalty,
                "retrieval_stage": sc.candidate.stage,
                "retrieval_reason": list(sc.reasons),
                "graph_distance": sc.graph_distance,
                "memory_match": None,
                "evidence_key": (
                    evidence.evidence_key if evidence is not None else None
                ),
                "project_file_id": (
                    evidence.project_file_id if evidence is not None else None
                ),
            })

        coverage = cov_svc.compute_intent_coverage(
            intents=requested_intents,
            results=result_dicts,
            sources_by_id=sources_by_id,
            literature_by_source_id=literature_by_source_id,
            graph_context=graph_context,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)

        run.status = RetrievalRunStatus.COMPLETED.value
        run.candidate_count = len(raw)
        run.final_result_count = len(final)
        run.duration_ms = duration_ms
        run.coverage = coverage
        run.warnings = warnings
        run.output_summary = {
            "result_count": len(final),
            "intents": requested_intents,
            "coverage_version": coverage.get("coverage_version"),
            "coverage_overall_score": coverage.get("overall_score"),
            "requirement_filter": requirement_filter_meta,
            "decomposition_version": (
                llm_dec_svc.LLM_DECOMPOSITION_VERSION
                if decomposition_used else None
            ),
            "decomposition_used": decomposition_used,
            "decomposition_fallback": decomposition_fallback,
            "subqueries": list(subqueries),
            "rerank_version": (
                llm_rerank_svc.LLM_RERANK_VERSION
                if rerank_used else None
            ),
            "rerank_used": rerank_used,
            "rerank_fallback": rerank_fallback,
            "graph_context_version": (
                graph_context.get("graph_context_version")
                if graph_context else None
            ),
            "graph_context_used": graph_context is not None,
        }
        run.completed_at = _now(db)

        if ctx.config.memory_enabled:
            try:
                mem_svc.learn_from_run(
                    db,
                    run=run,
                    project_id=ctx.project_id,
                    user_id=ctx.user_id,
                    results=result_dicts,
                )
            except Exception:
                logger.exception("rag_memory_learn_failed")
                warnings.append("memory_learn_failed")

        db.commit()
        db.refresh(run)
        return RetrievalOutcome(
            run=run,
            results=result_dicts,
            coverage=coverage,
            warnings=warnings,
            cached=False,
        )

    except Exception as exc:
        logger.exception("rag_retrieval_failed")
        db.rollback()
        try:
            duration_ms = int((time.perf_counter() - started) * 1000)
            failed = RetrievalRun(
                project_id=ctx.project_id,
                user_id=ctx.user_id,
                report_id=ctx.report_id,
                research_plan_id=ctx.plan.id if ctx.plan else None,
                plan_section_id=ctx.section.id if ctx.section else None,
                evidence_requirement_id=(
                    ctx.requirement.id if ctx.requirement else None
                ),
                graph_version_id=ctx.graph_version_id,
                query=ctx.query,
                normalized_query=ctx.normalized_query,
                query_hash=ctx.query_hash,
                context_hash=ctx.context_hash + ":failed",
                retrieval_version=ADVANCED_RAG_VERSION,
                ranking_model_version=RANKING_MODEL_VERSION,
                status=RetrievalRunStatus.FAILED.value,
                candidate_count=0,
                final_result_count=0,
                duration_ms=duration_ms,
                error_message=str(exc)[:500],
            )
            db.add(failed)
            db.commit()
        except Exception:
            logger.exception("rag_failure_persist_failed")
            db.rollback()
        raise


def _apply_memory_hints(
    db: Session, *, project_id: uuid.UUID, scored: list
) -> None:
    settings = get_settings()
    if settings.rag_memory_reuse_top_k <= 0:
        return
    memories = mem_svc.list_active_memories(
        db,
        project_id=project_id,
        memory_types=["query_result", "useful_source", "useful_chunk"],
        limit=settings.rag_memory_reuse_top_k,
    )
    if not memories:
        return
    from app.db.models.research_memory import ResearchMemoryLink
    mem_ids = [m.id for m in memories]
    links = list(db.execute(
        select(ResearchMemoryLink).where(
            ResearchMemoryLink.memory_id.in_(mem_ids)
        )
    ).scalars().all())
    boosts_by_source: dict[uuid.UUID, float] = {}
    for ln in links:
        if ln.linked_entity_type == "source":
            boosts_by_source[ln.linked_entity_id] = max(
                boosts_by_source.get(ln.linked_entity_id, 0.0), 0.15
            )
    if not boosts_by_source:
        return
    for sc in scored:
        b = boosts_by_source.get(sc.candidate.source_id)
        if b:
            sc.memory_score = b
            sc.final_score = min(1.0, sc.final_score + b)
            sc.reasons.append("memory_reuse")
    scored.sort(
        key=lambda s: (-s.final_score, str(s.candidate.chunk_id))
    )


def _result_to_dict(r: RetrievalResult) -> dict:
    result_meta = r.result_meta or {}
    return {
        "rank": r.rank,
        "chunk_id": r.chunk_id,
        "source_id": r.source_id,
        "final_score": float(r.final_score),
        "vector_score": (
            float(r.vector_score) if r.vector_score is not None else None
        ),
        "lexical_score": (
            float(r.lexical_score) if r.lexical_score is not None else None
        ),
        "graph_score": (
            float(r.graph_score) if r.graph_score is not None else None
        ),
        "memory_score": (
            float(r.memory_score) if r.memory_score is not None else None
        ),
        "quality_score": (
            float(r.quality_score) if r.quality_score is not None else None
        ),
        "diversity_penalty": (
            float(r.diversity_penalty)
            if r.diversity_penalty is not None else None
        ),
        "retrieval_stage": r.retrieval_stage,
        "retrieval_reason": list(r.retrieval_reason or []),
        "graph_distance": r.graph_distance,
        "memory_match": r.memory_match,
        "evidence_key": result_meta.get("evidence_key"),
        "project_file_id": result_meta.get("project_file_id"),
    }


__all__ = [
    "RetrievalRequest",
    "RetrievalOutcome",
    "retrieve_research_context",
]
