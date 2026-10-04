"""M26 — Worker handler for advanced RAG retrieval jobs."""
from __future__ import annotations

import logging

from pydantic import ValidationError

from app.core.exceptions import RetrievalAdvancedInvalid
from app.db.session import SessionLocal
from app.domain.embeddings import EmbeddingProfile
from app.integrations.embeddings.base import EmbeddingProvider
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.services.rag import context as ctx_svc
from app.services.rag.jobs import AdvancedRAGJobPayload
from app.services.rag.orchestrator import (
    RetrievalRequest,
    retrieve_research_context,
)

logger = logging.getLogger(__name__)


def handle_advanced_rag_retrieve(ctx) -> dict:
    raw_payload = ctx.payload or {}
    try:
        payload = AdvancedRAGJobPayload.model_validate(raw_payload)
    except ValidationError as exc:
        raise ValueError(
            f"invalid advanced_rag payload: {exc}"
        ) from exc

    with SessionLocal() as db:
        profile: EmbeddingProfile = get_current_embedding_profile()
        configured_provider: EmbeddingProvider | None = (
            build_embedding_provider(profile)
            if payload.mode in ("semantic", "hybrid")
            else None
        )
        provider = ctx_svc.provider_for_mode(
            mode=payload.mode,
            profile=profile,
            provider=configured_provider,
        )

        resolved = ctx_svc.resolve_retrieval_context(
            db,
            project_id=payload.project_id,
            user_id=payload.user_id,
            query=payload.query,
            provider=provider,
            profile=profile,
            report_id=payload.report_id,
            plan_section_id=payload.plan_section_id,
            evidence_requirement_id=payload.evidence_requirement_id,
            mode=payload.mode,
            algorithm=payload.algorithm,
            max_results=payload.max_results,
            graph_expansion_enabled=payload.graph_expansion_enabled,
            memory_enabled=payload.memory_enabled,
            diversity_enabled=payload.diversity_enabled,
            min_year=payload.min_year,
            max_year=payload.max_year,
            required_full_text=payload.required_full_text,
            allowed_source_ids=payload.allowed_source_ids,
        )

        if payload.context_hash != resolved.context_hash:
            raise RetrievalAdvancedInvalid(
                "stale retrieval context: "
                f"payload={payload.context_hash} "
                f"resolved={resolved.context_hash}"
            )

        request = RetrievalRequest(
            project_id=payload.project_id,
            user_id=payload.user_id,
            query=payload.query,
            provider=provider,
            profile=profile,
            report_id=payload.report_id,
            plan_section_id=payload.plan_section_id,
            evidence_requirement_id=payload.evidence_requirement_id,
            mode=payload.mode,
            algorithm=payload.algorithm,
            max_results=payload.max_results,
            graph_expansion_enabled=payload.graph_expansion_enabled,
            memory_enabled=payload.memory_enabled,
            diversity_enabled=payload.diversity_enabled,
            min_year=payload.min_year,
            max_year=payload.max_year,
            required_full_text=payload.required_full_text,
            allowed_source_ids=payload.allowed_source_ids,
        )
        outcome = retrieve_research_context(
            db, request=request, context=resolved
        )
        return {
            "status": outcome.run.status,
            "cached": outcome.cached,
            "run_id": str(outcome.run.id),
            "result_count": len(outcome.results),
        }


__all__ = ["handle_advanced_rag_retrieve"]
