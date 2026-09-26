"""M28 — Section research engine (deterministic orchestrator).

Consumes ManuscriptSection.research_contract, calls M26 once for the
section, selects evidence, evaluates coverage. Does NOT persist.
Persistence + idempotency + API + worker are Phase C.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    SectionResearchConfigurationInvalid,
    SectionResearchInvalid,
    SectionResearchNotFound,
)
from app.db.models.literature import ProjectLiteratureItem
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from app.db.models.source import Chunk, Source
from app.domain.embeddings import EmbeddingProfile
from app.domain.research_plan import RESEARCH_PLAN_REFERENCE_YEAR
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.services.projects import get_project
from app.services.reports import get_report
from app.services.section_research import context as ctx_svc
from app.services.section_research import coverage as cov_svc
from app.services.section_research import evidence as ev_svc
from app.services.section_research import filters as filt_svc
from app.services.section_research import query as q_svc
from app.services.section_research import retrieval as ret_svc
from app.services.section_research.contract import (
    ValidatedContract,
    validate_contract,
)

logger = logging.getLogger(__name__)


@dataclass
class SectionResearchResult:
    section_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    manuscript_id: uuid.UUID
    report_id: uuid.UUID
    project_id: uuid.UUID
    section_key: str
    contract_hash: str
    context_hash: str
    query_plan: q_svc.QueryPlan
    primary_query: str
    retrieval_run_id: uuid.UUID | None
    candidates_considered: int
    evidence: list[ev_svc.EvidenceItem]
    per_requirement: list[cov_svc.RequirementCoverage]
    coverage: cov_svc.SectionCoverage
    warnings: list[str] = field(default_factory=list)
    status: str = "completed"
    error_message: str | None = None
    duration_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "section_id": str(self.section_id),
            "manuscript_version_id": str(self.manuscript_version_id),
            "manuscript_id": str(self.manuscript_id),
            "report_id": str(self.report_id),
            "project_id": str(self.project_id),
            "section_key": self.section_key,
            "contract_hash": self.contract_hash,
            "context_hash": self.context_hash,
            "query_plan": self.query_plan.as_dict(),
            "primary_query": self.primary_query,
            "retrieval_run_id": (
                str(self.retrieval_run_id)
                if self.retrieval_run_id else None
            ),
            "candidates_considered": int(self.candidates_considered),
            "evidence": [e.as_dict() for e in self.evidence],
            "per_requirement": [
                r.as_dict() for r in self.per_requirement
            ],
            "coverage": self.coverage.as_dict(),
            "warnings": list(self.warnings),
            "status": self.status,
            "error_message": self.error_message,
            "duration_ms": int(self.duration_ms),
        }


# ---------- helpers ----------


def _load_manuscript_chain(
    db: Session, *, user_id: uuid.UUID, report_id: uuid.UUID,
    section_id: uuid.UUID,
) -> tuple[
    ManuscriptSection, ManuscriptVersion, Manuscript, uuid.UUID,
]:
    report = get_report(db, user_id=user_id, report_id=report_id)
    if report.project_id is None:
        raise SectionResearchInvalid("report has no project")

    section = db.get(ManuscriptSection, section_id)
    if section is None:
        raise SectionResearchNotFound()

    version = db.get(ManuscriptVersion, section.manuscript_version_id)
    if version is None:
        raise SectionResearchNotFound()

    manuscript = db.get(Manuscript, version.manuscript_id)
    if manuscript is None or manuscript.report_id != report_id:
        # Do not leak existence of foreign sections.
        raise SectionResearchNotFound()

    if manuscript.current_version_id != version.id:
        raise SectionResearchInvalid(
            "section is not in the manuscript's current version"
        )
    if version.status != "ready":
        raise SectionResearchInvalid("manuscript version is not ready")

    return section, version, manuscript, report.project_id


def _load_sources(
    db: Session, *, source_ids: set[uuid.UUID],
) -> dict[uuid.UUID, Source]:
    if not source_ids:
        return {}
    rows = db.execute(
        select(Source).where(Source.id.in_(list(source_ids)))
    ).scalars().all()
    return {s.id: s for s in rows}


def _load_literature(
    db: Session, *, project_id: uuid.UUID,
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
    return {r.source_id: r for r in rows}


def _load_chunk_contents(
    db: Session, *, chunk_ids: set[uuid.UUID],
) -> dict[uuid.UUID, str]:
    if not chunk_ids:
        return {}
    rows = db.execute(
        select(Chunk.id, Chunk.content).where(
            Chunk.id.in_(list(chunk_ids))
        )
    ).tuples().all()
    return dict(rows)


# ---------- engine ----------


def run_section_research(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    provider=None,
    profile: EmbeddingProfile | None = None,
) -> SectionResearchResult:
    started = time.perf_counter()
    settings = get_settings()

    if not settings.section_research_enabled:
        raise SectionResearchConfigurationInvalid(
            "section research is disabled"
        )

    section, version, manuscript, project_id = _load_manuscript_chain(
        db,
        user_id=user_id,
        report_id=report_id,
        section_id=section_id,
    )
    project = get_project(db, user_id=user_id, project_id=project_id)

    # 1) Contract validation (fail-closed)
    vc: ValidatedContract = validate_contract(
        contract=section.research_contract or {},
        section_key=section.section_key,
    )

    # 2) Query plan
    query_plan = q_svc.build_query_plan(
        research_objective=vc.research_objective,
        retrieval_intents=list(vc.retrieval_intents),
        max_queries=int(settings.section_research_max_queries),
    )

    # 3) Effective filters (deterministic)
    eff_filters, filter_warnings = filt_svc.build_effective_filters(
        source_constraints=vc.source_constraints,
        reference_year=RESEARCH_PLAN_REFERENCE_YEAR,
    )

    # 4) Provider/profile
    if profile is None:
        profile = get_current_embedding_profile()
    if provider is None:
        provider = build_embedding_provider(profile)

    # 5) Resolve M26 context (drives effective config + M26 context_hash)
    m26_ctx = ret_svc.resolve_section_retrieval_context(
        db,
        section=section,
        project_id=project.id,
        report_id=report_id,
        user_id=user_id,
        query=query_plan.primary,
        provider=provider,
        profile=profile,
        mode="lexical",
        algorithm="ann",
        max_results=None,
        min_year=eff_filters.min_year,
        max_year=eff_filters.max_year,
        required_full_text=eff_filters.required_full_text,
        allowed_source_ids=None,
    )

    # 6) M28 context hash (deterministic, independent from M26 hash)
    context_hash = ctx_svc.compute_section_research_context_hash(
        project_id=project.id,
        report_id=report_id,
        manuscript_version_id=version.id,
        manuscript_section_id=section.id,
        contract_hash=vc.contract_hash,
        profile=profile,
        mode=m26_ctx.mode,
        algorithm=m26_ctx.algorithm,
        effective_filters=eff_filters.as_dict(),
        effective_max_results=m26_ctx.config.max_results,
        candidate_limit=m26_ctx.config.candidate_limit,
    )

    # 7) Run M26
    warnings: list[str] = list(filter_warnings)
    outcome = None
    candidates: list[dict] = []
    try:
        bundle = ret_svc.execute_section_retrieval(
            db,
            section=section,
            project_id=project.id,
            report_id=report_id,
            user_id=user_id,
            query=query_plan.primary,
            provider=provider,
            profile=profile,
            context=m26_ctx,
        )
        outcome = bundle.outcome
        if outcome is not None:
            candidates = list(outcome.results or [])
        warnings.extend(bundle.warnings)
    except Exception as exc:
        logger.exception("section_research_m26_failed")
        duration_ms = int((time.perf_counter() - started) * 1000)
        return SectionResearchResult(
            section_id=section.id,
            manuscript_version_id=version.id,
            manuscript_id=manuscript.id,
            report_id=report_id,
            project_id=project.id,
            section_key=section.section_key,
            contract_hash=vc.contract_hash,
            context_hash=context_hash,
            query_plan=query_plan,
            primary_query=query_plan.primary,
            retrieval_run_id=None,
            candidates_considered=0,
            evidence=[],
            per_requirement=[],
            coverage=cov_svc.SectionCoverage(
                coverage_version="m28-coverage-v1",
                coverage_target=vc.coverage_target,
                coverage_score=0.0,
                coverage_state="insufficient",
            ),
            warnings=warnings,
            status="failed",
            error_message=str(exc)[:500],
            duration_ms=duration_ms,
        )

    # 8) Load sources + literature + chunks
    source_ids: set[uuid.UUID] = set()
    chunk_ids: set[uuid.UUID] = set()
    for c in candidates:
        sid = c.get("source_id")
        if sid is not None:
            source_ids.add(sid)
        cid = c.get("chunk_id")
        if cid is not None:
            chunk_ids.add(cid)

    sources_by_id = _load_sources(db, source_ids=source_ids)
    literature_by_source_id = _load_literature(
        db, project_id=project.id, source_ids=source_ids,
    )
    chunk_contents = _load_chunk_contents(db, chunk_ids=chunk_ids)

    # 9) Evidence selection
    selection = ev_svc.select_evidence(
        candidates=candidates,
        requirements=vc.evidence_requirements,
        sources_by_id=sources_by_id,
        literature_by_source_id=literature_by_source_id,
        chunk_contents=chunk_contents,
        excerpt_chars=int(settings.section_research_excerpt_chars),
        max_evidence=int(settings.section_research_max_evidence),
        per_source_cap=ev_svc.DEFAULT_PER_SOURCE_CAP,
        reference_year=RESEARCH_PLAN_REFERENCE_YEAR,
    )
    warnings.extend(selection.warnings)

    # 10) Coverage
    coverage = cov_svc.evaluate_section_coverage(
        requirements=vc.evidence_requirements,
        matches=selection.matches,
        coverage_target=vc.coverage_target,
        covered_threshold=float(
            settings.section_research_coverage_covered_threshold
        ),
        partial_threshold=float(
            settings.section_research_coverage_partial_threshold
        ),
    )
    warnings.extend(coverage.warnings)

    duration_ms = int((time.perf_counter() - started) * 1000)
    return SectionResearchResult(
        section_id=section.id,
        manuscript_version_id=version.id,
        manuscript_id=manuscript.id,
        report_id=report_id,
        project_id=project.id,
        section_key=section.section_key,
        contract_hash=vc.contract_hash,
        context_hash=context_hash,
        query_plan=query_plan,
        primary_query=query_plan.primary,
        retrieval_run_id=outcome.run.id if outcome else None,
        candidates_considered=len(candidates),
        evidence=selection.selected,
        per_requirement=coverage.per_requirement,
        coverage=coverage,
        warnings=warnings,
        status="completed",
        error_message=None,
        duration_ms=duration_ms,
    )


__all__ = ["SectionResearchResult", "run_section_research"]
