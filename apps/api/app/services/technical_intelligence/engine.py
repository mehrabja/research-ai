"""M29 — Deterministic orchestrator (role-aware)."""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import TechnicalIntelligenceConfigurationInvalid
from app.db.models.code_analysis import CodeAnalysis
from app.db.models.data_profile import DataProfile
from app.db.models.project_file import ProjectFile
from app.domain.technical_intelligence import (
    TechnicalIntelligenceRunStatus,
)
from app.services.technical_intelligence import artifact_role as role_svc
from app.services.technical_intelligence import artifacts as art_svc
from app.services.technical_intelligence import context as ctx_svc
from app.services.technical_intelligence import extraction as ex_svc
from app.services.technical_intelligence import result_parsing as rp_svc

logger = logging.getLogger(__name__)


@dataclass
class M29Result:
    project_id: uuid.UUID
    report_id: uuid.UUID | None
    context_hash: str
    facts: list[ex_svc.ExtractedFact] = field(default_factory=list)
    results: list[rp_svc.ParsedResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = TechnicalIntelligenceRunStatus.COMPLETED.value
    error_message: str | None = None
    duration_ms: int = 0


def run_technical_intelligence(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID | None = None,
    manuscript_version_id: uuid.UUID | None = None,
    context_hash: str | None = None,
) -> M29Result:
    started = time.perf_counter()
    settings = get_settings()
    if not settings.technical_intelligence_enabled:
        raise TechnicalIntelligenceConfigurationInvalid(
            "technical intelligence is disabled"
        )

    if context_hash is None:
        context_hash = ctx_svc.compute_m29_context_hash(
            db, project_id=project_id
        )

    max_facts = int(settings.technical_intelligence_max_facts)
    max_results = int(settings.technical_intelligence_max_results)
    max_metrics = int(settings.technical_intelligence_max_metrics)
    max_rows = int(settings.technical_intelligence_max_result_rows)
    max_files = int(settings.technical_intelligence_max_files)
    max_bytes = art_svc.max_result_bytes()

    files = list(db.execute(
        select(ProjectFile).where(
            ProjectFile.project_id == project_id,
            ProjectFile.deleted_at.is_(None),
        ).order_by(ProjectFile.id.asc()).limit(max_files)
    ).scalars().all())

    warnings: list[str] = []
    facts: list[ex_svc.ExtractedFact] = []
    results: list[rp_svc.ParsedResult] = []

    file_ids = [f.id for f in files]
    analyses_by_file: dict[uuid.UUID, CodeAnalysis] = {}
    profiles_by_file: dict[uuid.UUID, DataProfile] = {}

    if file_ids:
        ca_rows = list(db.execute(
            select(CodeAnalysis)
            .where(CodeAnalysis.project_file_id.in_(file_ids))
            .where(CodeAnalysis.parse_status == "completed")
        ).scalars().all())
        for ca in ca_rows:
            analyses_by_file[ca.project_file_id] = ca

        dp_rows = list(db.execute(
            select(DataProfile)
            .where(DataProfile.project_file_id.in_(file_ids))
            .where(DataProfile.profile_status == "completed")
        ).scalars().all())
        for dp in dp_rows:
            profiles_by_file[dp.project_file_id] = dp

    for pf in files:
        role = role_svc.detect_artifact_role(pf)

        if role_svc.is_source_code(role.role):
            analysis = analyses_by_file.get(pf.id)
            if analysis is None:
                continue
            if len(facts) >= max_facts:
                warnings.append("max_facts_reached")
                break
            facts.extend(ex_svc.extract_from_code_analysis(
                db,
                analysis=analysis,
                project_id=project_id,
                report_id=report_id,
                manuscript_version_id=manuscript_version_id,
                max_facts=max_facts - len(facts),
                context_hash=context_hash,
            ))
            continue

        if role_svc.is_configuration(role.role) or role_svc.is_dataset(
            role.role
        ):
            profile = profiles_by_file.get(pf.id)
            if profile is None:
                continue
            if len(facts) >= max_facts:
                warnings.append("max_facts_reached")
                break
            facts.extend(ex_svc.extract_from_data_profile(
                db,
                profile=profile,
                project_id=project_id,
                report_id=report_id,
                manuscript_version_id=manuscript_version_id,
                max_facts=max_facts - len(facts),
                context_hash=context_hash,
            ))
            continue

        if role_svc.is_experiment_result(role.role):
            if len(results) >= max_results:
                warnings.append("max_results_reached")
                break
            try:
                data, too_large = art_svc.read_bounded(
                    db,
                    project_file_id=pf.id,
                    max_bytes=max_bytes,
                )
            except Exception:
                logger.exception("m29_read_failed file_id=%s", pf.id)
                warnings.append(f"read_failed:{pf.id}")
                continue
            if too_large:
                warnings.append(f"artifact_too_large:{pf.id}")
                continue
            parsed, w = rp_svc.parse_results_from_raw_artifact(
                project_file=pf,
                data=data,
                max_rows=min(max_rows, max_results - len(results)),
                max_metrics=max_metrics,
                context_hash=context_hash,
            )
            warnings.extend(f"{pf.id}:{x}" for x in w)
            results.extend(parsed)
            continue

        warnings.append(f"skipped_unknown_role:{pf.id}")

    return M29Result(
        project_id=project_id,
        report_id=report_id,
        context_hash=context_hash,
        facts=facts,
        results=results,
        warnings=warnings,
        status=TechnicalIntelligenceRunStatus.COMPLETED.value,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


__all__ = ["M29Result", "run_technical_intelligence"]
