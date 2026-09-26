"""M23 — Deterministic context hash for literature intelligence.

Covers every input that affects pipeline output:
  * analysis version + reference year
  * project intent (objective / questions / hypotheses / scope / constraints)
  * project classification + referenced taxonomy identity/version
  * per-source metadata (title, year, doi, url, citation_count,
    source_quality, authors count, abstract length, status,
    content_hash, extracted_at)
  * per-source embedding signature (sorted chunk identities)
  * per-item screening + manual override + analysis_version
  * active project file ids

Two runs with the same hash + version are idempotent.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.literature import ProjectLiteratureItem
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report
from app.db.models.research_classification import ProjectClassification
from app.db.models.research_taxonomy import (
    PaperType as PaperTypeRow,
)
from app.db.models.research_taxonomy import (
    ResearchDesign as ResearchDesignRow,
)
from app.db.models.research_taxonomy import (
    ResearchDomain as ResearchDomainRow,
)
from app.db.models.source import Chunk, Source
from app.domain.literature import LITERATURE_INTELLIGENCE_VERSION


def _sha256_hex(parts: list[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def _json_canonical(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _project_source_ids(
    db: Session, *, project_id: uuid.UUID
) -> list[uuid.UUID]:
    report_ids = list(
        db.execute(
            select(Report.id).where(
                Report.project_id == project_id,
                Report.deleted_at.is_(None),
            )
        ).scalars().all()
    )
    if not report_ids:
        return []
    return list(
        db.execute(
            select(Source.id).where(Source.report_id.in_(report_ids))
        ).scalars().all()
    )


def _embedding_signature(
    db: Session, *, source_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Per-source sha256 over sorted chunk identities.

    Identity per chunk = (chunk_id, embedding_input_hash,
    embedding_model_version, embedding_status).

    Any change — including re-embedding with the same input hash but
    a different provider/model — flips the per-source signature.
    """
    if not source_ids:
        return {}
    rows = db.execute(
        select(
            Chunk.source_id,
            Chunk.id,
            Chunk.embedding_input_hash,
            Chunk.embedding_model_version,
            Chunk.embedding_status,
        ).where(Chunk.source_id.in_(source_ids))
    ).all()
    by_source: dict[uuid.UUID, list[tuple[str, str, str, str]]] = {}
    for sid, cid, ih, mv, status in rows:
        by_source.setdefault(sid, []).append(
            (str(cid), ih or "-", mv or "-", status or "-")
        )
    out: dict[uuid.UUID, str] = {}
    for sid, entries in by_source.items():
        entries.sort()
        h = hashlib.sha256()
        for e in entries:
            h.update("|".join(e).encode("utf-8"))
            h.update(b"\x00")
        out[sid] = h.hexdigest()[:24]
    return out


def _taxonomy_signature(
    db: Session, cls: ProjectClassification | None
) -> str:
    if cls is None:
        return "none"
    parts: list[str] = []
    if cls.domain_id:
        dom = db.get(ResearchDomainRow, cls.domain_id)
        if dom is not None:
            aliases = dom.aliases or []
            parts.append(
                "domain:"
                f"{dom.code}:"
                f"{dom.name}:"
                f"{dom.taxonomy_version or '-'}:"
                f"{','.join(sorted(str(a) for a in aliases))}"
            )
    if cls.paper_type_code:
        pt = db.execute(
            select(PaperTypeRow).where(
                PaperTypeRow.code == cls.paper_type_code
            )
        ).scalar_one_or_none()
        if pt is not None:
            parts.append(
                f"paper_type:{pt.code}:{pt.taxonomy_version or '-'}"
            )
    if cls.research_design_code:
        rd = db.execute(
            select(ResearchDesignRow).where(
                ResearchDesignRow.code == cls.research_design_code
            )
        ).scalar_one_or_none()
        if rd is not None:
            parts.append(
                f"design:{rd.code}:{rd.taxonomy_version or '-'}"
            )
    return "|".join(parts) if parts else "empty"


def build_literature_context_hash(
    db: Session, *, project_id: uuid.UUID
) -> str:
    parts: list[str] = [
        f"version:{LITERATURE_INTELLIGENCE_VERSION}",
        f"ref_year:{datetime.now(UTC).year}",
    ]

    proj = db.get(Project, project_id)
    if proj is not None:
        parts.append(
            "project_intent:"
            + _json_canonical(
                {
                    "objective": proj.research_objective,
                    "questions": proj.research_questions or [],
                    "hypotheses": proj.hypotheses or [],
                    "scope": proj.scope,
                    "constraints": proj.constraints,
                }
            )
        )
    else:
        parts.append("project_intent:none")

    cls = db.execute(
        select(ProjectClassification).where(
            ProjectClassification.project_id == project_id
        )
    ).scalar_one_or_none()
    if cls is None:
        parts.append("classification:none")
    else:
        parts.append(
            "classification:"
            f"{cls.domain_id or '-'}:"
            f"{cls.paper_type_code or '-'}:"
            f"{cls.research_design_code or '-'}:"
            f"{cls.status}:"
            f"{cls.classifier_version or '-'}"
        )
        parts.append(f"taxonomy:{_taxonomy_signature(db, cls)}")

    source_ids = _project_source_ids(db, project_id=project_id)
    if source_ids:
        emb_map = _embedding_signature(db, source_ids=source_ids)
        src_rows = db.execute(
            select(
                Source.id,
                Source.title,
                Source.status,
                Source.content_hash,
                Source.extracted_at,
                Source.citation_count,
                Source.year,
                Source.doi,
                Source.url,
                Source.source_quality,
                func.coalesce(func.length(Source.abstract), 0),
                func.coalesce(func.jsonb_array_length(Source.authors), 0),
            )
            .where(Source.id.in_(source_ids))
            .order_by(Source.id.asc())
        ).all()
        for row in src_rows:
            (
                sid, title, status, chash, extracted_at, cc, yr,
                doi, url, quality, abs_len, authors_len,
            ) = row
            emb_sig = emb_map.get(sid, "-")
            parts.append(
                f"src:{sid}:"
                f"title={title or '-'}:"
                f"status={status}:"
                f"chash={chash or '-'}:"
                f"extracted={(extracted_at.isoformat() if extracted_at else '-')}:"
                f"cc={cc or 0}:"
                f"yr={yr or 0}:"
                f"doi={1 if doi else 0}:"
                f"url={1 if url else 0}:"
                f"q={quality if quality is not None else '-'}:"
                f"abs={abs_len}:"
                f"auth={authors_len}:"
                f"emb={emb_sig}"
            )
    else:
        parts.append("sources:none")

    # Per-item state: only user-controlled bits go into the hash.
    # - analysis_version is a pipeline OUTPUT → must NOT invalidate.
    # - screening_status when manual_override=False is pipeline OUTPUT
    #   → must NOT invalidate.
    # - screening_status when manual_override=True is user INPUT
    #   → must invalidate.
    # Only user-controlled item state goes into the hash.
    # Auto-created items (screening_status from auto-screening,
    # analysis_version from pipeline) are OUTPUTS of the pipeline,
    # not inputs. Including them would break idempotency:
    #   run 1: items:none        → pipeline creates item
    #   run 2: item:...:mo=0     → different hash → never skips
    # Only rows with manual_override=True are user INPUT.
    manual_items = db.execute(
        select(
            ProjectLiteratureItem.id,
            ProjectLiteratureItem.source_id,
            ProjectLiteratureItem.screening_status,
            ProjectLiteratureItem.manual_override_at,
        ).where(
            ProjectLiteratureItem.project_id == project_id,
            ProjectLiteratureItem.manual_override.is_(True),
        )
    ).all()
    if manual_items:
        for it in sorted(manual_items, key=lambda r: str(r[0])):
            parts.append(
                f"manual-item:{it.id}:"
                f"src={it.source_id}:"
                f"screening={it.screening_status}:"
                f"moat="
                f"{it.manual_override_at.isoformat() if it.manual_override_at else '-'}"
            )
    else:
        parts.append("manual-items:none")

    file_ids = list(
        db.execute(
            select(ProjectFile.id).where(
                ProjectFile.project_id == project_id,
                ProjectFile.deleted_at.is_(None),
            )
        ).scalars().all()
    )
    for fid in sorted(file_ids, key=str):
        parts.append(f"file:{fid}")

    return _sha256_hex(parts)

__all__ = ["build_literature_context_hash"]
