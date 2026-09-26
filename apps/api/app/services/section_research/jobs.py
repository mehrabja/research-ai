"""M28 — Enqueue helper for section research jobs."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    SectionResearchNotFound,
)
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from app.db.models.report import Report
from app.domain.section_research import SECTION_RESEARCH_VERSION
from app.services import jobs as jobs_service
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.services.section_research import context as ctx_svc
from app.services.section_research import filters as filt_svc
from app.services.section_research import query as q_svc
from app.services.section_research import retrieval as ret_svc
from app.services.section_research.contract import validate_contract

logger = logging.getLogger(__name__)


def enqueue_section_research(
    db: Session,
    *,
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    user_id: uuid.UUID,
    force: bool = False,
) -> uuid.UUID:
    """Enqueue a section_research job.

    Raises:
        SectionResearchNotFound — if the chain does not resolve.
        Any job_service error is re-raised.
    """
    report = db.get(Report, report_id)
    if report is None or report.project_id is None:
        raise SectionResearchNotFound()

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
        raise SectionResearchNotFound()

    vc = validate_contract(
        contract=section.research_contract or {},
        section_key=section.section_key,
    )

    settings = get_settings()
    query_plan = q_svc.build_query_plan(
        research_objective=vc.research_objective,
        retrieval_intents=list(vc.retrieval_intents),
        max_queries=int(settings.section_research_max_queries),
    )
    eff_filters, _w = filt_svc.build_effective_filters(
        source_constraints=vc.source_constraints,
    )

    profile = get_current_embedding_profile()
    provider = build_embedding_provider(profile)

    m26_ctx = ret_svc.resolve_section_retrieval_context(
        db,
        section=section,
        project_id=report.project_id,
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
        project_id=report.project_id,
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

    payload = {
        "report_id": str(report_id),
        "section_id": str(section_id),
        "user_id": str(user_id),
        "context_hash": context_hash,
        "contract_hash": vc.contract_hash,
        "m28_version": SECTION_RESEARCH_VERSION,
        "force": bool(force),
    }

    enqueued = jobs_service.enqueue_job(
        db,
        job_type="section_research",
        payload=payload,
        idempotency_key=(
            f"section_research:{section_id}:"
            f"{context_hash}:{SECTION_RESEARCH_VERSION}"
        ),
        report_id=report_id,
        user_id=user_id,
        max_attempts=int(settings.section_research_job_max_attempts),
    )
    return enqueued.job.id


__all__ = ["enqueue_section_research"]
