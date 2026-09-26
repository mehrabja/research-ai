"""M32 — Deterministic context hash.

No datetime. No random. No secrets.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.citation import (
    CitationIdentity,
    CitationRun,
    Claim,
)
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.domain.humanization_m32 import (
    M32_PRESERVATION_VERSION,
    M32_VERSION,
)
from app.services.citation import prose as prose_svc


def _claim_fingerprints(
    db: Session, *, report_id: uuid.UUID,
) -> list[dict[str, Any]]:
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
        return []
    claims = list(db.execute(
        select(Claim).where(Claim.citation_run_id == run.id)
    ).scalars().all())
    return [
        {
            "claim_id": str(c.id),
            "claim_hash": c.claim_hash,
            "claim_type": c.claim_type,
        }
        for c in claims
    ]


def _citation_identity_fingerprints(
    db: Session, *, report_id: uuid.UUID,
) -> list[dict[str, Any]]:
    rows = list(db.execute(
        select(CitationIdentity)
        .where(CitationIdentity.report_id == report_id)
        .order_by(CitationIdentity.id.asc())
    ).scalars().all())
    return [
        {
            "identity_id": str(i.id),
            "identity_key": i.identity_key,
            "source_id": str(i.source_id),
        }
        for i in rows
    ]


def compute_m32_context_hash(
    db: Session,
    *,
    manuscript_version_id: uuid.UUID,
    mode: str,
) -> str:
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        return hashlib.sha256(b"missing-version").hexdigest()

    ms = db.get(Manuscript, version.manuscript_id)
    report = db.get(Report, ms.report_id) if ms else None
    report_id = report.id if report else None

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

    claims = _claim_fingerprints(db, report_id=report_id) if report_id else []
    identities = (
        _citation_identity_fingerprints(db, report_id=report_id)
        if report_id else []
    )

    payload: dict[str, Any] = {
        "m32_version": M32_VERSION,
        "preservation_version": M32_PRESERVATION_VERSION,
        "manuscript_version_id": str(manuscript_version_id),
        "manuscript_version_context_hash": version.context_hash,
        "mode": mode,
        "prose": prose_state,
        "claims": claims,
        "citation_identities": identities,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = ["compute_m32_context_hash"]
