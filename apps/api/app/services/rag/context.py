"""M26 — Resolved retrieval context (single source of truth).

Both sync and async paths call ``resolve_retrieval_context()``; nothing
else is allowed to independently resolve plan/section/requirement,
graph version, effective config, filters, or compute the context hash.

No network I/O. No DB mutations. Read-only SQL only.
"""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import cast, get_args

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import RetrievalAdvancedConfigurationInvalid, RetrievalAdvancedInvalid
from app.db.models.report import Report
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanSection,
)
from app.domain.embeddings import (
    EmbeddingBatchResult,
    EmbeddingProfile,
    build_embedding_profile_id,
)
from app.domain.retrieval import (
    RetrievalAlgorithm,
    RetrievalMode,
)
from app.integrations.embeddings.base import EmbeddingProvider
from app.services.knowledge_graph import context as kg_ctx
from app.services.rag import context_hash as ch_svc

_VALID_MODES = frozenset(get_args(RetrievalMode))
_VALID_ALGORITHMS = frozenset(get_args(RetrievalAlgorithm))


@dataclass(frozen=True)
class LexicalOnlyEmbeddingProvider:
    """Contract object used when retrieval mode does not need embeddings."""
    provider_name = "lexical-only"
    max_input_tokens_per_item: int | None = None
    max_input_tokens_per_request: int | None = None
    max_batch_size = 1
    model_name: str = field(init=False)
    dimensions: int = field(init=False)

    def __init__(self, profile: EmbeddingProfile) -> None:
        object.__setattr__(self, "model_name", profile.model)
        object.__setattr__(self, "dimensions", profile.dimensions)

    def estimate_input_tokens(self, text: str) -> int | None:
        return None

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        raise RetrievalAdvancedInvalid(
            "embedding provider is not available for lexical retrieval"
        )

    def embed_query(self, text: str) -> list[float]:
        raise RetrievalAdvancedInvalid(
            "embedding provider is not available for lexical retrieval"
        )


def provider_for_mode(
    *, mode: RetrievalMode, profile: EmbeddingProfile, provider: EmbeddingProvider | None
) -> EmbeddingProvider:
    if mode == "lexical":
        return provider if provider is not None else cast(EmbeddingProvider, LexicalOnlyEmbeddingProvider(profile))
    if provider is None:
        raise RetrievalAdvancedConfigurationInvalid(
            f"embedding provider required for {mode} retrieval"
        )
    return provider


@dataclass(frozen=True)
class EffectiveConfig:
    graph_enabled: bool
    memory_enabled: bool
    diversity_enabled: bool
    max_results: int
    candidate_limit: int


@dataclass(frozen=True)
class RetrievalFilters:
    min_year: int | None
    max_year: int | None
    required_full_text: bool
    allowed_source_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class ResolvedRetrievalContext:
    """Sole semantic retrieval context.

    API sync, API async, worker and orchestrator MUST consume the same
    resolved values. They MUST NOT independently resolve plan, section,
    requirement, graph version, effective flags, filters, or context
    hash.
    """

    project_id: uuid.UUID
    user_id: uuid.UUID
    query: str
    normalized_query: str
    query_hash: str

    report_id: uuid.UUID | None
    plan: ResearchPlan | None
    section: ResearchPlanSection | None
    requirement: ResearchEvidenceRequirement | None

    graph_version_id: uuid.UUID | None

    mode: RetrievalMode
    algorithm: RetrievalAlgorithm
    filters: RetrievalFilters

    config: EffectiveConfig

    profile_id: str
    context_hash: str

    provider: EmbeddingProvider
    profile: EmbeddingProfile


# -------- effective max (single source of truth) ------------------- #


def effective_max_results(
    *,
    request_max: int | None,
    settings,
) -> int:
    """Apply the runtime cap for effective max results."""
    return min(
        request_max
        if request_max is not None
        else settings.rag_max_results,
        settings.rag_max_results,
    )


# -------- resolution helpers --------------------------------------- #


def _resolve_plan_context(
    db: Session,
    *,
    project_id: uuid.UUID,
    section_id: uuid.UUID | None,
    requirement_id: uuid.UUID | None,
) -> tuple[
    ResearchPlan | None,
    ResearchPlanSection | None,
    ResearchEvidenceRequirement | None,
]:
    plan = db.execute(
        select(ResearchPlan)
        .where(
            ResearchPlan.project_id == project_id,
            ResearchPlan.status == "ready",
        )
        .order_by(ResearchPlan.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    section: ResearchPlanSection | None = None
    if section_id is not None:
        candidate = db.execute(
            select(ResearchPlanSection).where(
                ResearchPlanSection.id == section_id
            )
        ).scalar_one_or_none()
        if candidate is None:
            raise RetrievalAdvancedInvalid("plan section not found")
        if plan is None or candidate.plan_id != plan.id:
            raise RetrievalAdvancedInvalid(
                "plan section does not belong to the active plan"
            )
        section = candidate

    requirement: ResearchEvidenceRequirement | None = None
    if requirement_id is not None:
        candidate_r = db.execute(
            select(ResearchEvidenceRequirement).where(
                ResearchEvidenceRequirement.id == requirement_id
            )
        ).scalar_one_or_none()
        if candidate_r is None:
            raise RetrievalAdvancedInvalid(
                "evidence requirement not found"
            )
        if plan is None or candidate_r.plan_id != plan.id:
            raise RetrievalAdvancedInvalid(
                "evidence requirement does not belong to the active plan"
            )
        if section is not None and candidate_r.section_id != section.id:
            raise RetrievalAdvancedInvalid(
                "evidence requirement does not belong to the requested "
                "section"
            )
        requirement = candidate_r

    return plan, section, requirement


def _resolve_report(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID | None,
) -> None:
    if report_id is None:
        return
    row = db.execute(
        select(Report.id).where(
            Report.id == report_id,
            Report.project_id == project_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise RetrievalAdvancedInvalid(
            "report does not belong to project"
        )


def _build_filters(
    *,
    min_year: int | None,
    max_year: int | None,
    required_full_text: bool,
    allowed_source_ids: list[uuid.UUID] | None,
) -> RetrievalFilters:
    normalized_ids: tuple[uuid.UUID, ...] = ()
    if allowed_source_ids:
        normalized_ids = tuple(
            sorted(set(allowed_source_ids), key=str)
        )
    return RetrievalFilters(
        min_year=min_year,
        max_year=max_year,
        required_full_text=required_full_text,
        allowed_source_ids=normalized_ids,
    )


def _filters_hash_payload(
    *, mode: str, algorithm: str, filters: RetrievalFilters
) -> dict:
    return {
        "mode": mode,
        "algorithm": algorithm,
        "min_year": filters.min_year,
        "max_year": filters.max_year,
        "required_full_text": filters.required_full_text,
        "allowed_source_ids": [
            str(x) for x in filters.allowed_source_ids
        ],
    }


def _effective_config(
    *,
    settings,
    graph_enabled_override: bool | None,
    memory_enabled_override: bool | None,
    diversity_enabled_override: bool | None,
    max_results_override: int | None,
) -> EffectiveConfig:
    graph_enabled = (
        graph_enabled_override
        if graph_enabled_override is not None
        else settings.knowledge_graph_enabled
    )
    memory_enabled = (
        memory_enabled_override
        if memory_enabled_override is not None
        else settings.rag_memory_enabled
    )
    diversity_enabled = (
        diversity_enabled_override
        if diversity_enabled_override is not None
        else settings.rag_diversity_enabled
    )

    max_results = effective_max_results(
        request_max=max_results_override,
        settings=settings,
    )
    # The underlying M09/M11 retrieval enforces its own top_k cap.
    top_k_cap = settings.embedding_retrieval_top_k_max
    if max_results > top_k_cap:
        max_results = top_k_cap

    candidate_limit = min(
        max_results * settings.embedding_retrieval_candidate_multiplier,
        settings.rag_max_candidates,
        top_k_cap,
    )
    return EffectiveConfig(
        graph_enabled=graph_enabled,
        memory_enabled=memory_enabled,
        diversity_enabled=diversity_enabled,
        max_results=max_results,
        candidate_limit=candidate_limit,
    )


# -------- main entrypoint ------------------------------------------ #


def resolve_retrieval_context(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    provider: EmbeddingProvider | None,
    profile: EmbeddingProfile,
    report_id: uuid.UUID | None = None,
    plan_section_id: uuid.UUID | None = None,
    evidence_requirement_id: uuid.UUID | None = None,
    mode: RetrievalMode = "lexical",
    algorithm: RetrievalAlgorithm = "ann",
    max_results: int | None = None,
    graph_expansion_enabled: bool | None = None,
    memory_enabled: bool | None = None,
    diversity_enabled: bool | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    required_full_text: bool = False,
    allowed_source_ids: list[uuid.UUID] | None = None,
) -> ResolvedRetrievalContext:
    """Resolve every semantic input that affects retrieval results.

    Deterministic. Read-only. No network. Never mutates DB.
    """
    from app.services.rag import normalization as norm_svc

    settings = get_settings()

    if mode not in _VALID_MODES:
        raise RetrievalAdvancedInvalid(
            f"invalid retrieval mode: {mode!r}"
        )
    if algorithm not in _VALID_ALGORITHMS:
        raise RetrievalAdvancedInvalid(
            f"invalid retrieval algorithm: {algorithm!r}"
        )

    if max_results is not None and max_results < 1:
        raise RetrievalAdvancedInvalid("max_results must be >= 1")

    if (
        min_year is not None
        and max_year is not None
        and min_year > max_year
    ):
        raise RetrievalAdvancedInvalid(
            "min_year cannot exceed max_year"
        )

    normalized, qhash = norm_svc.normalize_and_hash(query)
    if not normalized:
        raise RetrievalAdvancedInvalid("empty query")

    _resolve_report(
        db, project_id=project_id, report_id=report_id
    )

    config = _effective_config(
        settings=settings,
        graph_enabled_override=graph_expansion_enabled,
        memory_enabled_override=memory_enabled,
        diversity_enabled_override=diversity_enabled,
        max_results_override=max_results,
    )

    plan, section, requirement = _resolve_plan_context(
        db,
        project_id=project_id,
        section_id=plan_section_id,
        requirement_id=evidence_requirement_id,
    )

    gv = (
        kg_ctx.active_graph_version(db, project_id=project_id)
        if config.graph_enabled
        else None
    )

    filters = _build_filters(
        min_year=min_year,
        max_year=max_year,
        required_full_text=required_full_text,
        allowed_source_ids=allowed_source_ids,
    )

    profile_id = build_embedding_profile_id(profile)

    context_hash = ch_svc.compute_retrieval_context_hash(
        db,
        project_id=project_id,
        report_id=report_id,
        query_hash=qhash,
        graph_version_id=gv.id if gv else None,
        plan_id=plan.id if plan else None,
        section_id=section.id if section else None,
        requirement_id=requirement.id if requirement else None,
        mode=mode,
        algorithm=algorithm,
        filters=_filters_hash_payload(
            mode=mode, algorithm=algorithm, filters=filters
        ),
        profile=profile,
        effective_graph_enabled=config.graph_enabled,
        effective_memory_enabled=config.memory_enabled,
        effective_diversity_enabled=config.diversity_enabled,
        effective_max_results=config.max_results,
        candidate_limit=config.candidate_limit,
    )

    resolved_provider = provider_for_mode(mode=mode, profile=profile, provider=provider)

    return ResolvedRetrievalContext(
        project_id=project_id,
        user_id=user_id,
        query=query,
        normalized_query=normalized,
        query_hash=qhash,
        report_id=report_id,
        plan=plan,
        section=section,
        requirement=requirement,
        graph_version_id=gv.id if gv else None,
        mode=mode,
        algorithm=algorithm,
        filters=filters,
        config=config,
        profile_id=profile_id,
        context_hash=context_hash,
        provider=resolved_provider,
        profile=profile,
    )


# -------- lock key helper ------------------------------------------ #


def compute_context_lock_key(
    *, project_id: uuid.UUID, context_hash: str
) -> int:
    """Deterministic signed-64-bit advisory lock key."""
    h = hashlib.sha256()
    h.update(str(project_id).encode("utf-8"))
    h.update(b"\x00")
    h.update(context_hash.encode("utf-8"))
    digest = h.digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


__all__ = [
    "EffectiveConfig",
    "RetrievalFilters",
    "ResolvedRetrievalContext",
    "effective_max_results",
    "resolve_retrieval_context",
    "compute_context_lock_key",
]
