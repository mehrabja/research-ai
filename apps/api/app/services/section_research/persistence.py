"""M28 — Idempotent persistence for section research runs.

Pattern:
    advisory lock (per section)
      → prepare (cheap, read-only)
      → lookup completed run for context_hash
      → if exists: append skipped run, reuse
      → else: execute engine, persist run + evidence atomically
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    SectionResearchConfigurationInvalid,
    SectionResearchInvalid,
    SectionResearchNotFound,
)
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.domain.research_plan import RESEARCH_PLAN_REFERENCE_YEAR
from app.domain.section_research import SECTION_RESEARCH_VERSION
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.services.section_research import context as ctx_svc
from app.services.section_research import engine as engine_svc
from app.services.section_research import filters as filt_svc
from app.services.section_research import query as q_svc
from app.services.section_research import retrieval as ret_svc
from app.services.section_research.contract import validate_contract

logger = logging.getLogger(__name__)


@dataclass
class PersistedSectionResearchResult:
    run: SectionResearchRun
    skipped: bool


def _lock_section(db: Session, *, section_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"section_research:{section_id}"},
    )


def _completed_run(
    db: Session,
    *,
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    context_hash: str,
) -> SectionResearchRun | None:
    from sqlalchemy import select

    return db.execute(
        select(SectionResearchRun).where(
            SectionResearchRun.report_id == report_id,
            SectionResearchRun.manuscript_section_id == section_id,
            SectionResearchRun.context_hash == context_hash,
            SectionResearchRun.m28_version == SECTION_RESEARCH_VERSION,
            SectionResearchRun.status == "completed",
        )
    ).scalar_one_or_none()


def _prepare_context_hash(
    db: Session,
    *,
    section: ManuscriptSection,
    version: ManuscriptVersion,
    manuscript: Manuscript,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[str, dict]:
    settings = get_settings()
    vc = validate_contract(
        contract=section.research_contract or {},
        section_key=section.section_key,
    )
    query_plan = q_svc.build_query_plan(
        research_objective=vc.research_objective,
        retrieval_intents=list(vc.retrieval_intents),
        max_queries=int(settings.section_research_max_queries),
    )
    eff_filters, _w = filt_svc.build_effective_filters(
        source_constraints=vc.source_constraints,
        reference_year=RESEARCH_PLAN_REFERENCE_YEAR,
    )
    profile = get_current_embedding_profile()
    provider = build_embedding_provider(profile)

    m26_ctx = ret_svc.resolve_section_retrieval_context(
        db,
        section=section,
        project_id=project_id,
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

    context_hash = ctx_svc.compute_section_research_context_hash(
        project_id=project_id,
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
    return context_hash, {
        "mode": m26_ctx.mode,
        "algorithm": m26_ctx.algorithm,
        "max_results": m26_ctx.config.max_results,
        "candidate_limit": m26_ctx.config.candidate_limit,
        "profile_id": m26_ctx.profile_id,
        "filters": eff_filters.as_dict(),
    }


def _evidence_role(
    matched_requirement_keys: list[str],
    required_keys: set[str],
) -> str:
    if any(k in required_keys for k in matched_requirement_keys):
        return "primary"
    return "support"


def run_section_research_persisted(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    force: bool = False,
    commit: bool = True,
) -> PersistedSectionResearchResult:
    settings = get_settings()
    if not settings.section_research_enabled:
        raise SectionResearchConfigurationInvalid(
            "section research is disabled"
        )

    section = db.get(ManuscriptSection, section_id)
    if section is None:
        raise SectionResearchNotFound()
    version = db.get(ManuscriptVersion, section.manuscript_version_id)
    if version is None:
        raise SectionResearchNotFound()
    manuscript = db.get(Manuscript, version.manuscript_id)
    if manuscript is None or manuscript.report_id != report_id:
        raise SectionResearchNotFound()
    if manuscript.current_version_id != version.id:
        raise SectionResearchInvalid(
            "section is not in the manuscript's current version"
        )
    project_id = manuscript.report_id  # placeholder; corrected below
    # Resolve real project_id via reports
    from app.db.models.report import Report
    report = db.get(Report, report_id)
    if report is None or report.project_id is None:
        raise SectionResearchInvalid("report has no project")
    project_id = report.project_id

    try:
        _lock_section(db, section_id=section_id)

        context_hash, retrieval_config = _prepare_context_hash(
            db,
            section=section,
            version=version,
            manuscript=manuscript,
            project_id=project_id,
            report_id=report_id,
            user_id=user_id,
        )

        existing = _completed_run(
            db,
            report_id=report_id,
            section_id=section_id,
            context_hash=context_hash,
        )
        if existing is not None:
            now = datetime.now(UTC)
            skipped = SectionResearchRun(
                project_id=project_id,
                report_id=report_id,
                manuscript_id=manuscript.id,
                manuscript_version_id=version.id,
                manuscript_section_id=section.id,
                context_hash=context_hash,
                contract_hash=existing.contract_hash,
                m28_version=SECTION_RESEARCH_VERSION,
                status="skipped",
                primary_query=existing.primary_query,
                query_plan=existing.query_plan,
                retrieval_config=retrieval_config,
                retrieval_run_id=existing.retrieval_run_id,
                candidate_count=existing.candidate_count,
                selected_evidence_count=existing.selected_evidence_count,
                coverage_score=existing.coverage_score,
                coverage_state=existing.coverage_state,
                coverage_summary=existing.coverage_summary,
                warnings=["reused_previous_completed_run"],
                duration_ms=0,
                completed_at=now,
            )
            db.add(skipped)
            if commit:
                db.commit()
                db.refresh(skipped)
            else:
                db.flush()
            return PersistedSectionResearchResult(
                run=skipped, skipped=True,
            )

        result = engine_svc.run_section_research(
            db,
            user_id=user_id,
            report_id=report_id,
            section_id=section_id,
        )

        required_keys = {
            r["requirement_key"]
            for r in (
                section.research_contract or {}
            ).get("evidence_requirements") or []
            if r.get("required")
        }

        now = datetime.now(UTC)
        run = SectionResearchRun(
            project_id=project_id,
            report_id=report_id,
            manuscript_id=manuscript.id,
            manuscript_version_id=version.id,
            manuscript_section_id=section.id,
            context_hash=result.context_hash,
            contract_hash=result.contract_hash,
            m28_version=SECTION_RESEARCH_VERSION,
            status=result.status,
            primary_query=result.primary_query,
            query_plan=result.query_plan.as_dict(),
            retrieval_config=retrieval_config,
            retrieval_run_id=result.retrieval_run_id,
            candidate_count=int(result.candidates_considered),
            selected_evidence_count=len(result.evidence),
            coverage_score=float(result.coverage.coverage_score),
            coverage_state=result.coverage.coverage_state,
            coverage_summary=result.coverage.as_dict(),
            warnings=list(result.warnings),
            error_message=result.error_message,
            duration_ms=int(result.duration_ms),
            completed_at=now,
        )
        db.add(run)
        db.flush()

        for idx, ev in enumerate(result.evidence, start=1):
            db.add(SectionResearchEvidence(
                research_run_id=run.id,
                project_id=project_id,
                source_id=ev.source_id,
                chunk_id=ev.chunk_id,
                rank=idx,
                final_score=float(ev.final_score),
                retrieval_stage=ev.retrieval_stage,
                retrieval_reason=list(ev.retrieval_reason),
                evidence_role=_evidence_role(
                    list(ev.matched_requirement_keys), required_keys,
                ),
                matched_requirement_keys=list(
                    ev.matched_requirement_keys
                ),
                citation_label=ev.citation_label,
                excerpt=ev.excerpt,
                evidence_meta=None,
            ))

        if commit:
            db.commit()
            db.refresh(run)
        else:
            db.flush()

        return PersistedSectionResearchResult(run=run, skipped=False)

    except Exception:
        logger.exception("section_research_persist_failed")
        if commit:
            db.rollback()
        raise


__all__ = [
    "PersistedSectionResearchResult",
    "run_section_research_persisted",
]
