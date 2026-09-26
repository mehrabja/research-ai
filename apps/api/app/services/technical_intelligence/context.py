"""M29 — Deterministic, content-based context hash.

No datetime. No random. No updated_at. Identity = immutable content.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.code_analysis import CodeAnalysis
from app.db.models.data_profile import DataProfile
from app.db.models.project_file import ProjectFile
from app.domain.technical_intelligence import (
    EXPERIMENT_KEY_MATCH_VERSION,
    M29_VERSION,
    RESULT_PARSER_VERSION,
    TECHNICAL_EXTRACTION_VERSION,
)


def _file_identity(pf: ProjectFile) -> dict[str, object]:
    return {
        "id": str(pf.id),
        "sha256": pf.sha256,
        "extension": (pf.extension or "").lower() or None,
        "size_bytes": pf.size_bytes,
        "file_kind": pf.file_kind,
    }

def compute_m29_context_hash(
    db: Session, *, project_id: uuid.UUID,
) -> str:
    files = list(db.execute(
        select(ProjectFile).where(
            ProjectFile.project_id == project_id,
            ProjectFile.deleted_at.is_(None),
        ).order_by(ProjectFile.id.asc())
    ).scalars().all())

    file_ids = [f.id for f in files]
    ca_rows: list[CodeAnalysis] = []
    dp_rows: list[DataProfile] = []
    if file_ids:
        ca_rows = list(db.execute(
            select(CodeAnalysis)
            .where(CodeAnalysis.project_file_id.in_(file_ids))
            .order_by(CodeAnalysis.id.asc())
        ).scalars().all())
        dp_rows = list(db.execute(
            select(DataProfile)
            .where(DataProfile.project_file_id.in_(file_ids))
            .order_by(DataProfile.id.asc())
        ).scalars().all())

    payload = {
        "m29_version": M29_VERSION,
        "extraction_version": TECHNICAL_EXTRACTION_VERSION,
        "result_parser_version": RESULT_PARSER_VERSION,
        "experiment_key_match_version": EXPERIMENT_KEY_MATCH_VERSION,
        "project_id": str(project_id),
        "files": [_file_identity(f) for f in files],
        "code_analyses": [
            {
                "id": str(a.id),
                "project_file_id": str(a.project_file_id),
                "analysis_version": a.analysis_version,
                "parser": a.parser,
                "parser_version": a.parser_version,
                "parse_status": a.parse_status,
            }
            for a in ca_rows
        ],
        "data_profiles": [
            {
                "id": str(p.id),
                "project_file_id": str(p.project_file_id),
                "profile_version": p.profile_version,
                "format": p.format,
                "profile_status": p.profile_status,
            }
            for p in dp_rows
        ],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = ["compute_m29_context_hash"]
