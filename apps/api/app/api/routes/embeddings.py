"""Embedding + retrieval routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.domain.embeddings import build_embedding_profile_id
from app.domain.retrieval import RETRIEVAL_ALGORITHM_VERSION
from app.schemas.embeddings import SourceEmbeddingResponse
from app.schemas.retrieval import (
    RetrievalCoverage,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedChunkResponse,
)
from app.services import embeddings as embeddings_service
from app.services import retrieval as retrieval_service
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.services.reports import get_report

router = APIRouter(prefix="/reports", tags=["embeddings"])




@router.post(
    "/{report_id}/sources/{source_id}/embed",
    response_model=SourceEmbeddingResponse,
    summary="Embed all stale chunks for a source",
)
def embed_source(
    report_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceEmbeddingResponse:
    # Enforce report ownership before resolving any external provider.
    get_report(db, user_id=current_user.id, report_id=report_id)
    profile = get_current_embedding_profile()
    result = embeddings_service.embed_source(
        db,
        user_id=current_user.id,
        report_id=report_id,
        source_id=source_id,
        provider=build_embedding_provider(profile),
        profile=profile,
    )
    return SourceEmbeddingResponse(
        source_id=result.source_id,
        total_chunks=result.total_chunks,
        already_current=result.already_current,
        embedded=result.embedded,
        failed=result.failed,
        pending=result.pending,
        profile_id=result.profile_id,
        usage_input_tokens=result.usage_input_tokens,
    )


@router.post(
    "/{report_id}/retrieve",
    response_model=RetrievalResponse,
    summary="Hybrid retrieval over the report's embedded corpus",
)
def retrieve(
    report_id: uuid.UUID,
    payload: RetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetrievalResponse:
    # Enforce report ownership before resolving any external provider.
    get_report(db, user_id=current_user.id, report_id=report_id)
    profile = get_current_embedding_profile()
    results, coverage = retrieval_service.retrieve(
        db,
        user_id=current_user.id,
        report_id=report_id,
        query=payload.query,
        top_k=payload.top_k,
        mode=payload.mode,
        algorithm="ann",
        source_ids=payload.source_ids,
        provider=build_embedding_provider(profile),
        profile=profile,
    )
    return RetrievalResponse(
        query=payload.query,
        mode=payload.mode,
        profile_id=build_embedding_profile_id(profile),
        retrieval_algorithm_version=RETRIEVAL_ALGORITHM_VERSION,
        coverage=RetrievalCoverage(
            total_chunks=coverage["total_chunks"],
            embedded_chunks=coverage["embedded_chunks"],
            pending_chunks=coverage["pending_chunks"],
            failed_chunks=coverage["failed_chunks"],
            stale_chunks=coverage["stale_chunks"],
        ),
        results=[
            RetrievedChunkResponse(
                evidence_id=r.evidence_id(),
                source_id=r.source_id,
                chunk_id=r.chunk_id,
                chunk_index=r.chunk_index,
                page_number=r.page_number,
                char_start=r.char_start,
                char_end=r.char_end,
                content=r.content,
                vector_similarity=r.vector_similarity,
                lexical_score=r.lexical_score,
                vector_rank=r.vector_rank,
                lexical_rank=r.lexical_rank,
                fusion_score=r.fusion_score,
                final_rank=r.final_rank,
            )
            for r in results
        ],
    )
