"""M28.5 — Deterministic content-based context hash."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.citation import CitationRun
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.db.models.research_plan import ResearchPlan
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.db.models.technical_intelligence import (
    TechnicalIntelligenceRun,
)
from app.domain.manuscript_prose import (
    M28_5_VERSION,
    PROSE_PROMPT_VERSION,
)


def _excerpt_hash(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def compute_m28_5_context_hash(
    db: Session,
    *,
    manuscript_version_id: uuid.UUID,
    mode: str,
    provider: str | None,
    model: str | None,
) -> str:
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        return hashlib.sha256(b"missing-version").hexdigest()

    ms = db.get(Manuscript, version.manuscript_id)
    report = db.get(Report, ms.report_id) if ms else None
    project_id = report.project_id if report else None
    report_id = report.id if report else None

    plan = db.get(ResearchPlan, version.research_plan_id)

    # M28 evidence fingerprints
    run_rows = list(db.execute(
        select(SectionResearchRun.id).where(
            SectionResearchRun.manuscript_version_id
            == manuscript_version_id,
            SectionResearchRun.status == "completed",
        ).order_by(SectionResearchRun.id.asc())
    ).all())
    run_ids = [r[0] for r in run_rows]
    evidence_fp: list[dict[str, Any]] = []
    if run_ids:
        rows = db.execute(
            select(
                SectionResearchEvidence.id,
                SectionResearchEvidence.research_run_id,
                SectionResearchEvidence.source_id,
                SectionResearchEvidence.excerpt,
                SectionResearchEvidence.rank,
            )
            .where(
                SectionResearchEvidence.research_run_id.in_(run_ids)
            )
            .order_by(SectionResearchEvidence.id.asc())
        ).all()
        for eid, rid, sid, exc, rank in rows:
            evidence_fp.append({
                "evidence_id": str(eid),
                "research_run_id": str(rid),
                "source_id": str(sid) if sid else None,
                "excerpt_hash": _excerpt_hash(exc),
                "rank": int(rank),
            })

    m29_fp: dict[str, Any] | None = None
    if project_id is not None:
        m29 = db.execute(
            select(TechnicalIntelligenceRun)
            .where(
                TechnicalIntelligenceRun.project_id == project_id,
                TechnicalIntelligenceRun.status == "completed",
            )
            .order_by(
                TechnicalIntelligenceRun.created_at.desc(),
                TechnicalIntelligenceRun.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if m29 is not None:
            m29_fp = {
                "run_id": str(m29.id),
                "context_hash": m29.context_hash,
                "m29_version": m29.m29_version,
            }

    m30_fp: dict[str, Any] | None = None
    if report_id is not None:
        m30 = db.execute(
            select(CitationRun)
            .where(
                CitationRun.report_id == report_id,
                CitationRun.status == "completed",
            )
            .order_by(
                CitationRun.created_at.desc(),
                CitationRun.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if m30 is not None:
            m30_fp = {
                "run_id": str(m30.id),
                "context_hash": m30.context_hash,
                "m30_version": m30.m30_version,
            }

    payload: dict[str, Any] = {
        "m28_5_version": M28_5_VERSION,
        "prompt_version": PROSE_PROMPT_VERSION,
        "mode": mode,
        "provider": provider,
        "model": model,
        "manuscript_version_id": str(manuscript_version_id),
        "manuscript_version_context_hash": version.context_hash,
        "research_plan": (
            {
                "plan_id": str(plan.id),
                "version": int(plan.version),
                "context_hash": plan.context_hash,
            }
            if plan else None
        ),
        "m28_evidence": evidence_fp,
        "m29_run": m29_fp,
        "m30_run": m30_fp,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = ["compute_m28_5_context_hash"]
