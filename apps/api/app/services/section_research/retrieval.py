"""M28 — M26 retrieval adapter (single call per section)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.exceptions import SectionResearchInvalid
from app.db.models.manuscript import ManuscriptSection
from app.domain.embeddings import EmbeddingProfile
from app.domain.retrieval import RetrievalAlgorithm, RetrievalMode
from app.integrations.embeddings.base import EmbeddingProvider
from app.services.rag.context import (
    ResolvedRetrievalContext,
    resolve_retrieval_context,
)
from app.services.rag.orchestrator import (
    RetrievalOutcome,
    RetrievalRequest,
    retrieve_research_context,
)


@dataclass(frozen=True)
class RetrievalBundle:
    context: ResolvedRetrievalContext
    outcome: RetrievalOutcome | None
    query: str
    warnings: list[str] = field(default_factory=list)


def resolve_section_retrieval_context(
    db: Session,
    *,
    section: ManuscriptSection,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    provider: EmbeddingProvider,
    profile: EmbeddingProfile,
    mode: RetrievalMode = "lexical",
    algorithm: RetrievalAlgorithm = "ann",
    max_results: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    required_full_text: bool = False,
    allowed_source_ids: list[uuid.UUID] | None = None,
) -> ResolvedRetrievalContext:
    plan_section_id = section.source_research_plan_section_id
    if plan_section_id is None:
        raise SectionResearchInvalid(
            "section has no source_research_plan_section_id"
        )
    return resolve_retrieval_context(
        db,
        project_id=project_id,
        user_id=user_id,
        query=query,
        provider=provider,
        profile=profile,
        report_id=report_id,
        plan_section_id=plan_section_id,
        evidence_requirement_id=None,
        mode=mode,
        algorithm=algorithm,
        max_results=max_results,
        min_year=min_year,
        max_year=max_year,
        required_full_text=required_full_text,
        allowed_source_ids=allowed_source_ids,
    )


def execute_section_retrieval(
    db: Session,
    *,
    section: ManuscriptSection,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    provider: EmbeddingProvider,
    profile: EmbeddingProfile,
    context: ResolvedRetrievalContext,
) -> RetrievalBundle:
    request = RetrievalRequest(
        project_id=project_id,
        user_id=user_id,
        query=query,
        provider=provider,
        profile=profile,
        report_id=report_id,
        plan_section_id=context.section.id if context.section else None,
        evidence_requirement_id=None,
        mode=context.mode,
        algorithm=context.algorithm,
        max_results=context.config.max_results,
        graph_expansion_enabled=context.config.graph_enabled,
        memory_enabled=context.config.memory_enabled,
        diversity_enabled=context.config.diversity_enabled,
        min_year=context.filters.min_year,
        max_year=context.filters.max_year,
        required_full_text=context.filters.required_full_text,
        allowed_source_ids=(
            list(context.filters.allowed_source_ids) or None
        ),
    )
    outcome = retrieve_research_context(
        db, request=request, context=context
    )
    return RetrievalBundle(
        context=context,
        outcome=outcome,
        query=query,
        warnings=list(outcome.warnings or []),
    )


__all__ = [
    "RetrievalBundle",
    "resolve_section_retrieval_context",
    "execute_section_retrieval",
]
