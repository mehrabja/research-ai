"""M23 — Deterministic literature clustering.

Method: per-source mean embedding (mean of chunk embeddings) →
cosine similarity ≥ threshold → connected components (union-find).

Bounds:
  * _MAX_CLUSTERABLE caps pairwise work; excess sources are skipped
    deterministically (top by relevance_score, id ASC).
  * _MAX_CLUSTER_SIZE caps component size; larger components are
    skipped (not truncated).

Does NOT commit — caller owns transaction.
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.literature import (
    LiteratureCluster,
    LiteratureClusterMember,
    ProjectLiteratureItem,
)
from app.db.models.source import Chunk
from app.domain.literature import CLUSTERING_VERSION

logger = logging.getLogger(__name__)

_SIM_THRESHOLD = 0.75
_MAX_CLUSTER_SIZE = 200
_MAX_CLUSTERABLE = 500


@dataclass
class ClusterAssignment:
    member_item_ids: list[uuid.UUID]
    similarities: list[float]


def _mean_embedding(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    dim = len(vectors[0])
    if dim == 0:
        return None
    kept = [v for v in vectors if len(v) == dim]
    if not kept:
        return None
    acc = [0.0] * dim
    for v in kept:
        for i, x in enumerate(v):
            acc[i] += x
    n = len(kept)
    return [x / n for x in acc]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _load_source_embeddings(
    db: Session, *, source_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[float]]:
    if not source_ids:
        return {}
    rows = db.execute(
        select(Chunk.source_id, Chunk.embedding).where(
            Chunk.source_id.in_(source_ids),
            Chunk.embedding.is_not(None),
            Chunk.embedding_status == "completed",
        )
    ).all()
    by_source: dict[uuid.UUID, list[list[float]]] = {}
    for sid, emb in rows:
        if emb is None:
            continue
        by_source.setdefault(sid, []).append(list(emb))
    out: dict[uuid.UUID, list[float]] = {}
    for sid, vecs in by_source.items():
        mean = _mean_embedding(vecs)
        if mean is not None:
            out[sid] = mean
    return out


class _UnionFind:
    def __init__(self, ids: list[uuid.UUID]) -> None:
        self._parent = {i: i for i in ids}

    def find(self, x: uuid.UUID) -> uuid.UUID:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: uuid.UUID, b: uuid.UUID) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


def _connected_components(
    item_ids: list[uuid.UUID],
    sims: dict[tuple[uuid.UUID, uuid.UUID], float],
    threshold: float,
) -> list[list[uuid.UUID]]:
    uf = _UnionFind(item_ids)
    for (a_id, b_id), s in sims.items():
        if s >= threshold:
            uf.union(a_id, b_id)
    groups: dict[uuid.UUID, list[uuid.UUID]] = {}
    for item_id in item_ids:
        r = uf.find(item_id)
        groups.setdefault(r, []).append(item_id)
    return [sorted(g, key=str) for g in groups.values()]


def cluster_project_literature(
    db: Session,
    *,
    project_id: uuid.UUID,
    replace_existing: bool = True,
) -> list[LiteratureCluster]:
    """Rebuild clusters for a project. Caller must commit."""
    items = list(
        db.execute(
            select(ProjectLiteratureItem).where(
                ProjectLiteratureItem.project_id == project_id,
                ProjectLiteratureItem.screening_status.in_(
                    ("candidate", "included")
                ),
            )
        ).scalars().all()
    )

    if replace_existing:
        existing_clusters = list(
            db.execute(
                select(LiteratureCluster).where(
                    LiteratureCluster.project_id == project_id
                )
            ).scalars().all()
        )
        for existing in existing_clusters:
            db.delete(existing)
        db.flush()

    if len(items) < 2:
        return []

    source_ids = [it.source_id for it in items]
    emb_map = _load_source_embeddings(db, source_ids=source_ids)

    clusterable = [
        it for it in items if emb_map.get(it.source_id) is not None
    ]
    if len(clusterable) < 2:
        return []

    clusterable.sort(
        key=lambda it: (
            -(float(it.relevance_score or 0.0)),
            str(it.id),
        )
    )
    skipped_by_cap = 0
    if len(clusterable) > _MAX_CLUSTERABLE:
        skipped_by_cap = len(clusterable) - _MAX_CLUSTERABLE
        logger.warning(
            "clustering_capped project_id=%s original=%d kept=%d",
            project_id, len(clusterable), _MAX_CLUSTERABLE,
        )
        clusterable = clusterable[:_MAX_CLUSTERABLE]

    sims: dict[tuple[uuid.UUID, uuid.UUID], float] = {}
    for i in range(len(clusterable)):
        left_item = clusterable[i]
        left_vec = emb_map[left_item.source_id]
        for j in range(i + 1, len(clusterable)):
            right_item = clusterable[j]
            s = _cosine(left_vec, emb_map[right_item.source_id])
            sims[(left_item.id, right_item.id)] = s

    components = _connected_components(
        [it.id for it in clusterable], sims, _SIM_THRESHOLD
    )
    skipped_oversize = 0
    kept_components: list[list[uuid.UUID]] = []
    for comp in components:
        if len(comp) < 2:
            continue
        if len(comp) > _MAX_CLUSTER_SIZE:
            skipped_oversize += 1
            logger.warning(
                "cluster_oversize project_id=%s size=%d cap=%d",
                project_id, len(comp), _MAX_CLUSTER_SIZE,
            )
            continue
        kept_components.append(comp)
    kept_components.sort(
        key=lambda comp: (len(comp), str(comp[0])), reverse=True
    )

    clusters: list[LiteratureCluster] = []
    for idx, member_ids in enumerate(kept_components, start=1):
        cluster = LiteratureCluster(
            project_id=project_id,
            name=f"Cluster {idx}",
            cluster_method="cosine_connected_components",
            cluster_version=CLUSTERING_VERSION,
            source_count=len(member_ids),
            status="completed",
            cluster_meta={
                "sim_threshold": _SIM_THRESHOLD,
                "skipped_by_cap": skipped_by_cap,
                "skipped_oversize": skipped_oversize,
            },
        )
        db.add(cluster)
        db.flush()

        member_id_set = set(member_ids)
        for member_id in member_ids:
            best = 0.0
            for (a_id, b_id), s in sims.items():
                if (a_id == member_id and b_id in member_id_set) or (
                    b_id == member_id and a_id in member_id_set
                ):
                    best = max(best, s)
            db.add(
                LiteratureClusterMember(
                    cluster_id=cluster.id,
                    literature_item_id=member_id,
                    similarity_score=round(best, 4),
                    membership_reason=(
                        f"cosine similarity >= {_SIM_THRESHOLD}"
                    ),
                )
            )
        clusters.append(cluster)

    db.flush()
    return clusters


__all__ = ["cluster_project_literature"]
