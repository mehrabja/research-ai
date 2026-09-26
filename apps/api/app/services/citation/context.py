"""M30 — Deterministic, content-based context hash.

No datetime. No random. No secrets.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.db.models.source import Source
from app.db.models.technical_intelligence import (
    TechnicalIntelligenceRun,
)
from app.domain.citation import (
    CLAIM_EXTRACTION_VERSION,
    M30_VERSION,
    REFERENCE_NORMALIZATION_VERSION,
)
from app.services.citation import prose as prose_svc


def _excerpt_hash(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _section_evidence_fingerprints(
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
            SectionResearchEvidence.evidence_role,
            SectionResearchEvidence.matched_requirement_keys,
            SectionResearchEvidence.rank,
        )
        .where(SectionResearchEvidence.research_run_id.in_(run_ids))
        .order_by(SectionResearchEvidence.id.asc())
    ).all()
    out: list[dict[str, Any]] = []
    for eid, rid, sid, cid, exc, role, mrk, rank in rows:
        entry: dict[str, Any] = {
            "evidence_id": str(eid),
            "research_run_id": str(rid),
            "source_id": str(sid) if sid else None,
            "chunk_id": str(cid) if cid else None,
            "excerpt_hash": _excerpt_hash(exc),
            "evidence_role": role,
            "matched_requirement_keys": list(mrk or []),
            "rank": int(rank),
        }
        out.append(entry)
    return out


def _current_m29_run_fingerprint(
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
    fingerprint: dict[str, Any] = {
        "run_id": str(run.id),
        "context_hash": run.context_hash,
        "m29_version": run.m29_version,
        "fact_count": int(run.fact_count),
        "result_count": int(run.result_count),
        "metric_count": int(run.metric_count),
    }
    return fingerprint


def _source_identity_fingerprints(
    db: Session, *, report_id: uuid.UUID,
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            Source.id,
            Source.doi,
            Source.title,
            Source.year,
            Source.authors,
        )
        .where(Source.report_id == report_id)
        .order_by(Source.id.asc())
    ).all()
    out: list[dict[str, Any]] = []
    for sid, doi, title, year, authors in rows:
        entry: dict[str, Any] = {
            "source_id": str(sid),
            "doi": (doi or None),
            "title": (title or None),
            "year": int(year) if year else None,
            "authors_count": len(authors or []),
        }
        out.append(entry)
    return out


def compute_m30_context_hash(
    db: Session,
    *,
    manuscript_version_id: uuid.UUID,
    citation_style: str,
) -> str:
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        return hashlib.sha256(b"missing-version").hexdigest()

    ms = db.get(Manuscript, version.manuscript_id)
    report = db.get(Report, ms.report_id) if ms else None
    project_id = report.project_id if report else None

    prose = prose_svc.get_manuscript_prose(
        db, manuscript_version_id=manuscript_version_id,
    )
    if prose is None:
        prose_state: dict[str, Any] = {
            "available": False,
            "content_hash": None,
            "section_count": 0,
        }
    else:
        prose_state = {
            "available": True,
            "content_hash": prose.content_hash,
            "section_count": len(prose.sections),
        }

    m28 = _section_evidence_fingerprints(
        db, manuscript_version_id=manuscript_version_id,
    )

    m29: dict[str, Any] | None = None
    if project_id is not None:
        m29 = _current_m29_run_fingerprint(
            db, project_id=project_id,
        )

    sources: list[dict[str, Any]] = []
    if report is not None:
        sources = _source_identity_fingerprints(
            db, report_id=report.id,
        )

    payload: dict[str, Any] = {
        "m30_version": M30_VERSION,
        "claim_extraction_version": CLAIM_EXTRACTION_VERSION,
        "reference_normalization_version":
            REFERENCE_NORMALIZATION_VERSION,
        "citation_style": citation_style,
        "manuscript_version_id": str(manuscript_version_id),
        "manuscript_version_context_hash": version.context_hash,
        "prose": prose_state,
        "m28_evidence": m28,
        "m29_run": m29,
        "sources": sources,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = ["compute_m30_context_hash"]
