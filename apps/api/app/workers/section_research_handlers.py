"""M28 — Worker handler for section_research jobs (stale-safe)."""
from __future__ import annotations

import logging
import uuid

from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from app.db.models.report import Report
from app.db.session import SessionLocal
from app.domain.section_research import SECTION_RESEARCH_VERSION
from app.services.embedding_profile import (
    build_embedding_provider,
    get_current_embedding_profile,
)
from app.services.section_research import context as ctx_svc
from app.services.section_research import filters as filt_svc
from app.services.section_research import persistence as persist_svc
from app.services.section_research import query as q_svc
from app.services.section_research import retrieval as ret_svc
from app.services.section_research.contract import validate_contract

logger = logging.getLogger(__name__)


def _parse_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def handle_section_research(ctx) -> dict:
    payload = ctx.payload or {}
    report_id = _parse_uuid(payload.get("report_id"))
    section_id = _parse_uuid(payload.get("section_id"))
    if report_id is None or section_id is None:
        raise ValueError("section_research payload missing ids")

    user_id = _parse_uuid(payload.get("user_id"))
    payload_context_hash = payload.get("context_hash")
    payload_contract_hash = payload.get("contract_hash")
    payload_m28_version = payload.get("m28_version")
    force = bool(payload.get("force", False))

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        if report is None or report.project_id is None:
            return {
                "status": "skipped", "skipped": True,
                "reason": "report_has_no_project",
            }
        effective_user_id = user_id or report.user_id

        section = db.get(ManuscriptSection, section_id)
        if section is None:
            return {
                "status": "skipped", "skipped": True,
                "reason": "section_not_found",
            }
        version = db.get(ManuscriptVersion, section.manuscript_version_id)
        if version is None:
            return {
                "status": "skipped", "skipped": True,
                "reason": "version_not_found",
            }
        manuscript = db.get(Manuscript, version.manuscript_id)
        if manuscript is None or manuscript.report_id != report_id:
            return {
                "status": "skipped", "skipped": True,
                "reason": "manuscript_mismatch",
            }
        if manuscript.current_version_id != version.id:
            return {
                "status": "skipped", "skipped": True,
                "reason": "stale_version",
            }

        # Recompute current context_hash from the real, current contract
        try:
            vc = validate_contract(
                contract=section.research_contract or {},
                section_key=section.section_key,
            )
        except Exception:
            return {
                "status": "skipped", "skipped": True,
                "reason": "contract_invalid",
            }

        settings_queries = int(
            __import__(
                "app.core.config", fromlist=["get_settings"],
            ).get_settings().section_research_max_queries
        )
        query_plan = q_svc.build_query_plan(
            research_objective=vc.research_objective,
            retrieval_intents=list(vc.retrieval_intents),
            max_queries=settings_queries,
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
            user_id=effective_user_id,
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
        current_context_hash = (
            ctx_svc.compute_section_research_context_hash(
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
        )

        stale_reason: str | None = None
        if payload_context_hash and payload_context_hash != (
            current_context_hash
        ):
            stale_reason = "stale_context"
        elif payload_contract_hash and payload_contract_hash != (
            vc.contract_hash
        ):
            stale_reason = "stale_contract"
        elif payload_m28_version and payload_m28_version != (
            SECTION_RESEARCH_VERSION
        ):
            stale_reason = "stale_version"

        if stale_reason is not None:
            logger.info(
                "section_research_stale report_id=%s section_id=%s "
                "reason=%s",
                report_id, section_id, stale_reason,
            )
            return {
                "status": "skipped", "skipped": True,
                "reason": stale_reason,
                "payload_context_hash": payload_context_hash,
                "current_context_hash": current_context_hash,
            }

        persisted = persist_svc.run_section_research_persisted(
            db,
            user_id=effective_user_id,
            report_id=report_id,
            section_id=section_id,
            force=force,
            commit=True,
        )
        return {
            "status": persisted.run.status,
            "skipped": persisted.skipped,
            "run_id": str(persisted.run.id),
            "context_hash": persisted.run.context_hash,
            "contract_hash": persisted.run.contract_hash,
        }


__all__ = ["handle_section_research"]
