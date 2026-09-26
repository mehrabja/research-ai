"""M23 — Deterministic cluster synthesis.

No LLM. Aggregates structured fields from member items. Detects
contradictions when two members disagree on outcome direction.

Does NOT commit — caller owns transaction.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.literature import (
    LiteratureCluster,
    LiteratureClusterMember,
    ProjectLiteratureItem,
)
from app.domain.literature import SYNTHESIS_VERSION

logger = logging.getLogger(__name__)

_POSITIVE_SIGNALS = {
    "effective", "significant", "improved", "superior",
    "beneficial", "positive",
}
_NEGATIVE_SIGNALS = {
    "ineffective", "no significant", "no effect", "not significant",
    "no improvement", "no benefit", "negative",
}


def _member_items(
    db: Session, *, cluster_id
) -> list[ProjectLiteratureItem]:
    ids = list(
        db.execute(
            select(LiteratureClusterMember.literature_item_id).where(
                LiteratureClusterMember.cluster_id == cluster_id
            )
        ).scalars().all()
    )
    if not ids:
        return []
    return list(
        db.execute(
            select(ProjectLiteratureItem).where(
                ProjectLiteratureItem.id.in_(ids)
            )
        ).scalars().all()
    )


def _detect_disagreements(
    items: list[ProjectLiteratureItem],
) -> list[dict]:
    out: list[dict] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a = items[i]
            b = items[j]
            ta = (a.findings_summary or "").lower()
            tb = (b.findings_summary or "").lower()
            if not ta or not tb:
                continue
            a_pos = any(w in ta for w in _POSITIVE_SIGNALS)
            a_neg = any(w in ta for w in _NEGATIVE_SIGNALS)
            b_pos = any(w in tb for w in _POSITIVE_SIGNALS)
            b_neg = any(w in tb for w in _NEGATIVE_SIGNALS)
            if (a_pos and b_neg) or (a_neg and b_pos):
                out.append(
                    {
                        "claim_a": ta[:200],
                        "claim_b": tb[:200],
                        "source_a": str(a.source_id),
                        "source_b": str(b.source_id),
                        "confidence": 0.55,
                    }
                )
    return out


def _aggregate_themes(
    items: list[ProjectLiteratureItem],
) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        for t in (it.themes or []):
            if isinstance(t, str) and t not in seen:
                seen.add(t)
                out.append(t)
    return out


def _aggregate_keywords(
    items: list[ProjectLiteratureItem],
) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        for k in (it.keywords or []):
            if isinstance(k, str) and k not in seen:
                seen.add(k)
                out.append(k)
    return out


def _evidence_strength(
    items: list[ProjectLiteratureItem],
) -> float:
    scores = [
        float(it.relevance_score)
        for it in items
        if it.relevance_score is not None
    ]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


def synthesize_cluster(
    db: Session, *, cluster: LiteratureCluster
) -> None:
    items = _member_items(db, cluster_id=cluster.id)
    if not items:
        cluster.status = "completed"
        cluster.summary = "empty cluster"
        db.flush()
        return

    themes = _aggregate_themes(items)
    keywords = _aggregate_keywords(items)
    disagreements = _detect_disagreements(items)
    limitations = [
        it.limitations_summary
        for it in items
        if it.limitations_summary
    ]

    representative = [
        str(it.source_id)
        for it in sorted(
            items,
            key=lambda i: float(i.relevance_score or 0),
            reverse=True,
        )[:3]
    ]

    top_kw = ", ".join(keywords[:5]) if keywords else "no keywords"
    cluster.name = f"Cluster: {top_kw}"
    cluster.summary = (
        f"{len(items)} sources; themes={len(themes)}; "
        f"keywords={top_kw}; disagreements={len(disagreements)}"
    )
    cluster.themes = themes or None
    cluster.keywords = keywords or None
    cluster.disagreements = disagreements or None
    cluster.limitations = limitations or None
    cluster.representative_source_ids = representative
    cluster.evidence_strength = Decimal(
        str(_evidence_strength(items))
    )
    cluster.status = "completed"
    cluster.cluster_meta = {"synthesis_version": SYNTHESIS_VERSION}
    db.flush()


def synthesize_project_clusters(
    db: Session, *, project_id
) -> int:
    clusters = list(
        db.execute(
            select(LiteratureCluster).where(
                LiteratureCluster.project_id == project_id
            )
        ).scalars().all()
    )
    for c in clusters:
        synthesize_cluster(db, cluster=c)
    db.flush()
    return len(clusters)


__all__ = ["synthesize_cluster", "synthesize_project_clusters"]
