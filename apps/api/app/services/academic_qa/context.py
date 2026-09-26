"""M31 — Deterministic, content-based context hash.

No datetime. No random. No secrets.
"""
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
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.db.models.technical_intelligence import (
    TechnicalIntelligenceRun,
)
from app.domain.academic_qa import (
    M31_VERSION,
    QA_RULES_VERSION,
)


def _excerpt_hash(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _evidence_fingerprints(
    db: Session, *, manuscript_version_id: uuid.UUID,
) -> list[dict[str, Any]]:
    run_ids = [
        r[0]
        for r in db.execute(
            select(SectionResearchRun.id).where(
                SectionResearchRun.manuscript_version_id
                == manuscript_version_id,
                SectionResearchRun.status == "completed",
            ).order_by(SectionResearchRun.id.asc())
        ).all()
    ]
    if not run_ids:
        return []
    rows = db.execute(
        select(
            SectionResearchEvidence.id,
            SectionResearchEvidence.research_run_id,
            SectionResearchEvidence.source_id,
            SectionResearchEvidence.chunk_id,
            SectionResearchEvidence.excerpt,
            SectionResearchEvidence.rank,
        )
        .where(SectionResearchEvidence.research_run_id.in_(run_ids))
        .order_by(SectionResearchEvidence.id.asc())
    ).all()
    return [
        {
            "evidence_id": str(eid),
            "research_run_id": str(rid),
            "source_id": str(sid) if sid else None,
            "chunk_id": str(cid) if cid else None,
            "excerpt_hash": _excerpt_hash(exc),
            "rank": int(rank),
        }
        for eid, rid, sid, cid, exc, rank in rows
    ]


def _current_m29_fingerprint(
    db: Session, *, project_id: uuid.UUID,
) -> dict[str, Any] | None:
    run = db.execute(
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
    if run is None:
        return None
    return {
        "run_id": str(run.id),
        "context_hash": run.context_hash,
        "m29_version": run.m29_version,
    }


def _current_m30_fingerprint(
    db: Session, *, report_id: uuid.UUID,
) -> dict[str, Any] | None:
    run = db.execute(
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
    if run is None:
        return None
    return {
        "run_id": str(run.id),
        "context_hash": run.context_hash,
        "m30_version": run.m30_version,
        "citation_style": run.citation_style,
    }


def compute_m31_context_hash(
    db: Session, *, manuscript_version_id: uuid.UUID,
) -> str:
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        return hashlib.sha256(b"missing-version").hexdigest()

    ms = db.get(Manuscript, version.manuscript_id)
    report = db.get(Report, ms.report_id) if ms else None
    project_id = report.project_id if report else None
    report_id = report.id if report else None

    evidence = _evidence_fingerprints(
        db, manuscript_version_id=manuscript_version_id,
    )
    m29 = (
        _current_m29_fingerprint(db, project_id=project_id)
        if project_id else None
    )
    m30 = (
        _current_m30_fingerprint(db, report_id=report_id)
        if report_id else None
    )

    payload: dict[str, Any] = {
        "m31_version": M31_VERSION,
        "rules_version": QA_RULES_VERSION,
        "manuscript_version_id": str(manuscript_version_id),
        "manuscript_version_context_hash": version.context_hash,
        "m28_evidence": evidence,
        "m29_run": m29,
        "m30_run": m30,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = ["compute_m31_context_hash"]
