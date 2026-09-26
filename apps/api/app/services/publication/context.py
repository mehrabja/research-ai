"""M33 — Deterministic context hash.

Includes target profile fingerprint so changing a target version
invalidates a prior compliance run.
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
from app.db.models.publication import PublicationTarget
from app.db.models.report import Report
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.domain.publication import (
    COMPLIANCE_RULES_VERSION,
    M33_VERSION,
    PUBLICATION_PROFILE_SCHEMA_VERSION,
)


def _target_fingerprint(target: PublicationTarget) -> dict[str, Any]:
    """Deterministic fingerprint of a target profile version.

    Uses persisted fields only. No timestamps.
    """
    return {
        "target_id": str(target.id),
        "target_code": target.target_code,
        "profile_version": target.profile_version,
        "profile_schema_version": target.profile_schema_version,
        "venue": target.venue,
        "venue_type": target.venue_type,
        "citation_style": target.citation_style,
        "paper_types": target.paper_types,
        "formatting_rules": target.formatting_rules,
        "section_rules": target.section_rules,
        "word_limits": target.word_limits,
        "abstract_limits": target.abstract_limits,
        "keyword_rules": target.keyword_rules,
        "author_rules": target.author_rules,
        "anonymity_rules": target.anonymity_rules,
        "figure_table_rules": target.figure_table_rules,
        "supplementary_rules": target.supplementary_rules,
        "reference_rules": target.reference_rules,
        "submission_checklist": target.submission_checklist,
    }


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
            "excerpt_hash": _excerpt_hash(exc),
            "rank": int(rank),
        }
        for eid, rid, sid, exc, rank in rows
    ]


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


def compute_m33_context_hash(
    db: Session,
    *,
    manuscript_version_id: uuid.UUID,
    target_id: uuid.UUID,
) -> str:
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        return hashlib.sha256(b"missing-version").hexdigest()

    target = db.get(PublicationTarget, target_id)
    if target is None:
        return hashlib.sha256(b"missing-target").hexdigest()

    ms = db.get(Manuscript, version.manuscript_id)
    report = db.get(Report, ms.report_id) if ms else None
    report_id = report.id if report else None

    evidence = _evidence_fingerprints(
        db, manuscript_version_id=manuscript_version_id,
    )
    m30 = _current_m30_fingerprint(db, report_id=report_id) if report_id else None

    payload: dict[str, Any] = {
        "m33_version": M33_VERSION,
        "rules_version": COMPLIANCE_RULES_VERSION,
        "profile_schema_version": PUBLICATION_PROFILE_SCHEMA_VERSION,
        "manuscript_version_id": str(manuscript_version_id),
        "manuscript_version_context_hash": version.context_hash,
        "target": _target_fingerprint(target),
        "m28_evidence": evidence,
        "m30_run": m30,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = ["compute_m33_context_hash"]
