"""M26 — Advanced RAG & Research Memory routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import (
    RetrievalAdvancedConfigurationInvalid,
    RetrievalAdvancedNotFound,
)
from app.db.models.research_memory import ResearchMemory
from app.db.models.retrieval import RetrievalResult, RetrievalRun
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.retrieval_advanced import (
    CoverageRead,
    MemoryListResponse,
    MemoryRead,
    RetrievalRunRead,
    RetrievedChunkRead,
    RetrieveRequest,
    RetrieveResponse,
)
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.services.projects import get_project
from app.services.rag import context as ctx_svc
from app.services.rag import jobs as rag_jobs
from app.services.rag.jobs import AdvancedRAGJobPayload
from app.services.rag.orchestrator import (
    RetrievalRequest,
    retrieve_research_context,
)

router = APIRouter(prefix="/projects", tags=["advanced-rag"])


def _result_row_to_read(r: RetrievalResult) -> RetrievedChunkRead:
    return RetrievedChunkRead(
        rank=r.rank,
        evidence_key=(
            f"retrieval_chunk:{r.chunk_id}" if r.chunk_id is not None else None
        ),
        chunk_id=r.chunk_id,
        source_id=r.source_id,
        final_score=float(r.final_score),
        vector_score=(
            float(r.vector_score) if r.vector_score is not None else None
        ),
        lexical_score=(
            float(r.lexical_score)
            if r.lexical_score is not None else None
        ),
        graph_score=(
            float(r.graph_score) if r.graph_score is not None else None
        ),
        memory_score=(
            float(r.memory_score)
            if r.memory_score is not None else None
        ),
        quality_score=(
            float(r.quality_score)
            if r.quality_score is not None else None
        ),
        diversity_penalty=(
            float(r.diversity_penalty)
            if r.diversity_penalty is not None else None
        ),
        retrieval_stage=r.retrieval_stage,
        retrieval_reason=list(r.retrieval_reason or []),
        graph_distance=r.graph_distance,
        memory_match=r.memory_match,
        evidence_key=(r.result_meta or {}).get("evidence_key"),
        project_file_id=_project_file_id_from_result(r),
    )


def _project_file_id_from_result(r: RetrievalResult) -> uuid.UUID | None:
    metadata = r.result_meta or {}
    raw = metadata.get("project_file_id")
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw))
    except (TypeError, ValueError):
        return None


@router.post(
    "/{project_id}/rag/retrieve",
    response_model=RetrieveResponse,
)
def retrieve(
    project_id: uuid.UUID,
    body: RetrieveRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetrieveResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    settings = get_settings()
    if not settings.rag_enabled:
        raise RetrievalAdvancedConfigurationInvalid("rag is disabled")

    profile = get_current_embedding_profile()
    provider = build_embedding_provider(profile)

    # Resolve context ONCE. Sync and async both consume this object.
    ctx = ctx_svc.resolve_retrieval_context(
        db,
        project_id=project_id,
        user_id=current_user.id,
        query=body.query,
        provider=provider,
        profile=profile,
        report_id=body.report_id,
        plan_section_id=body.plan_section_id,
        evidence_requirement_id=body.evidence_requirement_id,
        mode=body.mode or "lexical",
        algorithm=body.algorithm or "ann",
        max_results=body.max_results,
        graph_expansion_enabled=body.graph_expansion_enabled,
        memory_enabled=body.memory_enabled,
        diversity_enabled=body.diversity_enabled,
        min_year=body.min_year,
        max_year=body.max_year,
        required_full_text=body.required_full_text,
        allowed_source_ids=body.allowed_source_ids,
    )

    effective_async = (
        settings.rag_async_jobs if body.async_ is None else body.async_
    )

    if effective_async:
        payload_model = AdvancedRAGJobPayload(
            project_id=project_id,
            user_id=current_user.id,
            query=body.query,
            context_hash=ctx.context_hash,
            report_id=ctx.report_id,
            plan_section_id=(
                ctx.section.id if ctx.section else None
            ),
            evidence_requirement_id=(
                ctx.requirement.id if ctx.requirement else None
            ),
            mode=ctx.mode,
            algorithm=ctx.algorithm,
            max_results=ctx.config.max_results,
            graph_expansion_enabled=ctx.config.graph_enabled,
            memory_enabled=ctx.config.memory_enabled,
            diversity_enabled=ctx.config.diversity_enabled,
            min_year=ctx.filters.min_year,
            max_year=ctx.filters.max_year,
            required_full_text=ctx.filters.required_full_text,
            allowed_source_ids=(
                list(ctx.filters.allowed_source_ids) or None
            ),
        )
        job_id = rag_jobs.enqueue_advanced_rag_retrieve(
            db, payload=payload_model
        )
        if job_id is None:
            response.status_code = 500
            return RetrieveResponse(status="failed")
        response.status_code = 202
        return RetrieveResponse(status="queued", job_id=job_id)

    outcome = retrieve_research_context(
        db,
        request=RetrievalRequest(
            project_id=project_id,
            user_id=current_user.id,
            query=body.query,
            provider=provider,
            profile=profile,
            report_id=body.report_id,
            plan_section_id=body.plan_section_id,
            evidence_requirement_id=body.evidence_requirement_id,
            mode=ctx.mode,
            algorithm=ctx.algorithm,
            max_results=body.max_results,
            graph_expansion_enabled=body.graph_expansion_enabled,
            memory_enabled=body.memory_enabled,
            diversity_enabled=body.diversity_enabled,
            min_year=body.min_year,
            max_year=body.max_year,
            required_full_text=body.required_full_text,
            allowed_source_ids=body.allowed_source_ids,
        ),
        context=ctx,
    )
    response.status_code = 200
    return RetrieveResponse(
        status=outcome.run.status,
        run=RetrievalRunRead.model_validate(outcome.run),
        results=[
            RetrievedChunkRead.model_validate(r) for r in outcome.results
        ],
        coverage=(
            CoverageRead.model_validate(outcome.coverage)
            if outcome.coverage else None
        ),
        warnings=outcome.warnings,
    )


@router.get(
    "/{project_id}/rag/runs/{run_id}",
    response_model=RetrieveResponse,
)
def get_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetrieveResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    run = db.execute(
        select(RetrievalRun).where(
            RetrievalRun.id == run_id,
            RetrievalRun.project_id == project_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise RetrievalAdvancedNotFound()
    rows = list(db.execute(
        select(RetrievalResult)
        .where(RetrievalResult.retrieval_run_id == run.id)
        .order_by(RetrievalResult.rank.asc())
    ).scalars().all())
    return RetrieveResponse(
        status=run.status,
        run=RetrievalRunRead.model_validate(run),
        results=[_result_row_to_read(r) for r in rows],
        coverage=(
            CoverageRead.model_validate(run.coverage)
            if run.coverage else None
        ),
        warnings=list(run.warnings or []),
    )


@router.get(
    "/{project_id}/rag/memory",
    response_model=MemoryListResponse,
)
def list_memory(
    project_id: uuid.UUID,
    memory_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    stmt = select(ResearchMemory).where(
        ResearchMemory.project_id == project_id
    )
    if memory_type:
        stmt = stmt.where(ResearchMemory.memory_type == memory_type)
    stmt = stmt.order_by(
        ResearchMemory.created_at.desc(),
        ResearchMemory.id.asc(),
    ).limit(limit)
    rows = list(db.execute(stmt).scalars().all())
    return MemoryListResponse(
        items=[MemoryRead.model_validate(r) for r in rows],
        total=len(rows),
    )
