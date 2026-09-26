"""M23 — Evidence-backed research gap detection.

Every gap has a deterministic fingerprint so reruns do not create
duplicates. User-reviewed gaps (status != candidate) are preserved
across recomputes and their fingerprints suppress candidate
re-creation.

Does NOT commit — caller owns transaction.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.literature import (
    LiteratureCluster,
    LiteratureGap,
    ProjectLiteratureItem,
)
from app.domain.literature import GAP_DETECTION_VERSION

logger = logging.getLogger(__name__)

_MIN_SOURCES_FOR_ANALYSIS = 5
_RECENT_YEARS = 5


def _fingerprint(
    *,
    gap_type: str,
    title: str,
    source_ids: list | None,
    cluster_ids: list | None,
) -> str:
    payload = {
        "gap_type": gap_type,
        "title": title,
        "source_ids": sorted(str(s) for s in (source_ids or [])),
        "cluster_ids": sorted(str(c) for c in (cluster_ids or [])),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _included_items(
    db: Session, *, project_id: uuid.UUID
) -> list[ProjectLiteratureItem]:
    return list(
        db.execute(
            select(ProjectLiteratureItem).where(
                ProjectLiteratureItem.project_id == project_id,
                ProjectLiteratureItem.screening_status.in_(
                    ("candidate", "included")
                ),
            )
        ).scalars().all()
    )


def _clear_auto_gaps(
    db: Session, *, project_id: uuid.UUID
) -> None:
    """Remove only auto-generated candidate gaps.

    Gaps a user has moved to reviewed/accepted/rejected are kept.
    """
    rows = list(
        db.execute(
            select(LiteratureGap).where(
                LiteratureGap.project_id == project_id,
                LiteratureGap.status == "candidate",
            )
        ).scalars().all()
    )
    for g in rows:
        db.delete(g)
    db.flush()


def _detect_evidence_gap(
    items: list[ProjectLiteratureItem],
    *,
    project_id: uuid.UUID,
) -> LiteratureGap | None:
    if len(items) >= _MIN_SOURCES_FOR_ANALYSIS:
        return None
    title = (
        "No literature screened as candidate or included"
        if not items
        else (
            f"Only {len(items)} sources below threshold "
            f"({_MIN_SOURCES_FOR_ANALYSIS})"
        )
    )
    description = (
        "The project has no candidate/included sources after "
        "screening. Evidence synthesis cannot proceed."
        if not items
        else (
            f"Only {len(items)} candidate/included sources. This is "
            f"below the minimum ({_MIN_SOURCES_FOR_ANALYSIS}) for "
            "meaningful synthesis."
        )
    )
    src_ids = [str(i.source_id) for i in items]
    return LiteratureGap(
        project_id=project_id,
        gap_type="evidence_gap",
        title=title,
        description=description,
        confidence=0.9 if not items else 0.7,
        supporting_source_ids=src_ids,
        supporting_cluster_ids=[],
        evidence_summary=(
            "absence_pattern:items==0"
            if not items
            else f"absence_pattern:items<{_MIN_SOURCES_FOR_ANALYSIS}"
        ),
        status="candidate",
        analysis_version=GAP_DETECTION_VERSION,
        fingerprint=_fingerprint(
            gap_type="evidence_gap",
            title=title,
            source_ids=src_ids,
            cluster_ids=[],
        ),
    )


def _detect_temporal_gap(
    items: list[ProjectLiteratureItem],
    sources_by_id: Mapping[uuid.UUID, object],
    *,
    project_id: uuid.UUID,
) -> LiteratureGap | None:
    years: list[int] = []
    for it in items:
        src = sources_by_id.get(it.source_id)
        y = getattr(src, "year", None) if src else None
        if isinstance(y, int):
            years.append(y)
    if not years:
        return None
    current = datetime.now(UTC).year
    if not all(y < current - _RECENT_YEARS for y in years):
        return None
    src_ids = [
        str(it.source_id)
        for it in items
        if sources_by_id.get(it.source_id) is not None
    ]
    title = "No recent literature"
    return LiteratureGap(
        project_id=project_id,
        gap_type="temporal_gap",
        title=title,
        description=(
            f"All {len(years)} sources with a year are older than "
            f"{_RECENT_YEARS} years. Recent evidence is missing."
        ),
        confidence=0.7,
        supporting_source_ids=src_ids,
        supporting_cluster_ids=[],
        evidence_summary=f"max_year={max(years)}",
        status="candidate",
        analysis_version=GAP_DETECTION_VERSION,
        fingerprint=_fingerprint(
            gap_type="temporal_gap",
            title=title,
            source_ids=src_ids,
            cluster_ids=[],
        ),
    )


def _detect_population_gap(
    items: list[ProjectLiteratureItem],
    *,
    project_id: uuid.UUID,
) -> LiteratureGap | None:
    pops = [
        (it.population or "").strip().lower()
        for it in items
        if it.population and it.population.strip()
    ]
    if not pops:
        return None
    counts = Counter(pops)
    top, _ = counts.most_common(1)[0]
    under = [
        it for it in items
        if (it.population or "").strip().lower() != top
        and it.population
    ]
    if not under:
        return None
    src_ids = [str(i.source_id) for i in under]
    title = f"Under-represented populations beyond '{top}'"
    return LiteratureGap(
        project_id=project_id,
        gap_type="population_gap",
        title=title,
        description=(
            "Most sources focus on a single population; other "
            "populations appear only sporadically."
        ),
        confidence=0.55,
        supporting_source_ids=src_ids,
        supporting_cluster_ids=[],
        evidence_summary=f"dominant_population={top}",
        status="candidate",
        analysis_version=GAP_DETECTION_VERSION,
        fingerprint=_fingerprint(
            gap_type="population_gap",
            title=title,
            source_ids=src_ids,
            cluster_ids=[],
        ),
    )


def _detect_contradiction_gaps(
    db: Session, *, project_id: uuid.UUID
) -> list[LiteratureGap]:
    clusters = list(
        db.execute(
            select(LiteratureCluster).where(
                LiteratureCluster.project_id == project_id
            )
        ).scalars().all()
    )
    out: list[LiteratureGap] = []
    for c in clusters:
        disagreements = c.disagreements or []
        if not disagreements:
            continue
        src_ids = sorted(
            {
                d.get("source_a")
                for d in disagreements
                if d.get("source_a")
            }
            | {
                d.get("source_b")
                for d in disagreements
                if d.get("source_b")
            }
        )
        cluster_ids = [str(c.id)]
        title = f"Conflicting findings in '{c.name}'"
        out.append(
            LiteratureGap(
                project_id=project_id,
                gap_type="contradiction_gap",
                title=title,
                description=(
                    f"{len(disagreements)} disagreement(s) detected "
                    "within this cluster."
                ),
                confidence=0.65,
                supporting_source_ids=src_ids,
                supporting_cluster_ids=cluster_ids,
                evidence_summary=(
                    f"disagreements={len(disagreements)}"
                ),
                status="candidate",
                analysis_version=GAP_DETECTION_VERSION,
                fingerprint=_fingerprint(
                    gap_type="contradiction_gap",
                    title=title,
                    source_ids=src_ids,
                    cluster_ids=cluster_ids,
                ),
            )
        )
    return out


def detect_project_gaps(
    db: Session,
    *,
    project_id: uuid.UUID,
    sources_by_id: Mapping[uuid.UUID, object],
) -> int:
    """Rebuild auto-gaps. Caller must commit.

    * candidate gaps are cleared and rebuilt;
    * reviewed/accepted/rejected gaps are preserved;
    * a preserved fingerprint suppresses a matching new candidate;
    * unique partial index (project_id, fingerprint) prevents races.
    """
    _clear_auto_gaps(db, project_id=project_id)
    items = _included_items(db, project_id=project_id)

    candidates: list[LiteratureGap] = []
    g = _detect_evidence_gap(items, project_id=project_id)
    if g:
        candidates.append(g)
    g = _detect_temporal_gap(
        items, sources_by_id, project_id=project_id
    )
    if g:
        candidates.append(g)
    g = _detect_population_gap(items, project_id=project_id)
    if g:
        candidates.append(g)
    candidates.extend(
        _detect_contradiction_gaps(db, project_id=project_id)
    )

    preserved_fps = set(
        db.execute(
            select(LiteratureGap.fingerprint).where(
                LiteratureGap.project_id == project_id,
                LiteratureGap.fingerprint.is_not(None),
                LiteratureGap.status != "candidate",
            )
        ).scalars().all()
    )

    inserted = 0
    for gap in candidates:
        if gap.fingerprint and gap.fingerprint in preserved_fps:
            continue
        db.add(gap)
        inserted += 1
    db.flush()
    return inserted


__all__ = ["detect_project_gaps"]
