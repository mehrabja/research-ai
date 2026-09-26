"""M26 — Research Memory service."""
from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.research_memory import (
    ResearchMemory,
    ResearchMemoryLink,
)
from app.db.models.retrieval import RetrievalRun
from app.domain.retrieval_advanced import MemoryStatus, MemoryType

logger = logging.getLogger(__name__)


def _fingerprint(
    memory_type: str,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    summary: str,
) -> str:
    h = hashlib.sha256()
    h.update(memory_type.encode("utf-8"))
    h.update(b"|")
    h.update((entity_type or "-").encode("utf-8"))
    h.update(b"|")
    h.update((str(entity_id) if entity_id else "-").encode("utf-8"))
    h.update(b"|")
    h.update(summary[:512].encode("utf-8"))
    return h.hexdigest()[:32]


def upsert_memory(
    db: Session,
    *,
    project_id: uuid.UUID,
    memory_type: str,
    summary: str,
    canonical_entity_type: str | None = None,
    canonical_entity_id: uuid.UUID | None = None,
    importance: float = 0.5,
    confidence: float = 0.5,
    source_run_id: uuid.UUID | None = None,
    meta: dict | None = None,
) -> ResearchMemory:
    fp = _fingerprint(
        memory_type, canonical_entity_type, canonical_entity_id, summary
    )
    existing = db.execute(
        select(ResearchMemory).where(
            ResearchMemory.project_id == project_id,
            ResearchMemory.memory_type == memory_type,
            ResearchMemory.content_fingerprint == fp,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.reuse_count = int(existing.reuse_count or 0) + 1
        if source_run_id and existing.source_run_id is None:
            existing.source_run_id = source_run_id
        db.flush()
        return existing

    mem = ResearchMemory(
        project_id=project_id,
        memory_type=memory_type,
        status=MemoryStatus.ACTIVE.value,
        content_fingerprint=fp,
        canonical_entity_type=canonical_entity_type,
        canonical_entity_id=canonical_entity_id,
        summary=summary,
        importance=importance,
        confidence=confidence,
        source_run_id=source_run_id,
        memory_meta=meta or {},
        reuse_count=0,
    )
    db.add(mem)
    db.flush()
    return mem


def link_memory(
    db: Session,
    *,
    memory_id: uuid.UUID,
    project_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    relation: str = "references",
    weight: float = 1.0,
) -> None:
    existing = db.execute(
        select(ResearchMemoryLink).where(
            ResearchMemoryLink.memory_id == memory_id,
            ResearchMemoryLink.linked_entity_type == entity_type,
            ResearchMemoryLink.linked_entity_id == entity_id,
            ResearchMemoryLink.relation == relation,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(ResearchMemoryLink(
        memory_id=memory_id,
        project_id=project_id,
        linked_entity_type=entity_type,
        linked_entity_id=entity_id,
        relation=relation,
        weight=weight,
    ))


def list_active_memories(
    db: Session,
    *,
    project_id: uuid.UUID,
    memory_types: list[str] | None = None,
    limit: int = 100,
) -> list[ResearchMemory]:
    settings = get_settings()
    min_imp = settings.rag_memory_min_importance
    stmt = select(ResearchMemory).where(
        ResearchMemory.project_id == project_id,
        ResearchMemory.status == MemoryStatus.ACTIVE.value,
        ResearchMemory.importance >= min_imp,
    )
    if memory_types:
        stmt = stmt.where(
            ResearchMemory.memory_type.in_(memory_types)
        )
    stmt = stmt.order_by(
        ResearchMemory.importance.desc(),
        ResearchMemory.created_at.desc(),
        ResearchMemory.id.asc(),
    ).limit(limit)
    return list(db.execute(stmt).scalars().all())


def learn_from_run(
    db: Session,
    *,
    run: RetrievalRun,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    results: list,
) -> None:
    settings = get_settings()
    if not settings.rag_memory_enabled:
        return
    if not results:
        return
    try:
        summary = (
            f"query='{run.normalized_query[:120]}' "
            f"results={len(results)}"
        )
        mem = upsert_memory(
            db,
            project_id=project_id,
            memory_type=MemoryType.QUERY_RESULT.value,
            summary=summary,
            importance=0.6,
            confidence=0.7,
            source_run_id=run.id,
            meta={"query_hash": run.query_hash},
        )
        for r in results[: settings.rag_memory_reuse_top_k]:
            chunk_id = getattr(r, "chunk_id", None) or (
                r.get("chunk_id") if isinstance(r, dict) else None
            )
            source_id = getattr(r, "source_id", None) or (
                r.get("source_id") if isinstance(r, dict) else None
            )
            if chunk_id:
                link_memory(
                    db,
                    memory_id=mem.id,
                    project_id=project_id,
                    entity_type="chunk",
                    entity_id=chunk_id,
                    relation="returned_in_run",
                )
            if source_id:
                link_memory(
                    db,
                    memory_id=mem.id,
                    project_id=project_id,
                    entity_type="source",
                    entity_id=source_id,
                    relation="returned_in_run",
                )
        db.flush()
    except Exception:
        logger.exception("rag_memory_learn_failed")


__all__ = [
    "upsert_memory",
    "link_memory",
    "list_active_memories",
    "learn_from_run",
]
