"""M24 — Deterministic context hash."""
from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.literature import (
    LiteratureCluster,
    LiteratureGap,
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.project import Project
from app.db.models.research_classification import ProjectClassification
from app.db.models.research_taxonomy import PaperType as PaperTypeRow
from app.db.models.research_taxonomy import ResearchDesign as ResearchDesignRow
from app.db.models.source import Source
from app.domain.research_plan import (
    RESEARCH_PLAN_COVERAGE_MODEL_VERSION,
    RESEARCH_PLAN_REFERENCE_YEAR,
    RESEARCH_PLAN_TEMPLATE_VERSION,
    RESEARCH_PLAN_VERSION,
)


def _json(value) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _sha256(parts: list[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def _latest_completed_run(
    db: Session, *, project_id: uuid.UUID
) -> LiteratureIntelligenceRun | None:
    return db.execute(
        select(LiteratureIntelligenceRun)
        .where(
            LiteratureIntelligenceRun.project_id == project_id,
            LiteratureIntelligenceRun.status == "completed",
        )
        .order_by(
            LiteratureIntelligenceRun.created_at.desc(),
            LiteratureIntelligenceRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def build_research_planning_context(
    db: Session, *, project_id: uuid.UUID
) -> dict:
    project = db.get(Project, project_id)
    classification = db.execute(
        select(ProjectClassification).where(
            ProjectClassification.project_id == project_id
        )
    ).scalar_one_or_none()
    run = _latest_completed_run(db, project_id=project_id)

    gaps: list[LiteratureGap] = []
    clusters: list[LiteratureCluster] = []
    items: list[ProjectLiteratureItem] = []
    sources_by_id: dict[uuid.UUID, Source] = {}
    included = 0
    candidates = 0

    if run is not None:
        gaps = list(
            db.execute(
                select(LiteratureGap).where(
                    LiteratureGap.project_id == project_id,
                    LiteratureGap.status.in_(
                        ("candidate", "reviewed", "accepted")
                    ),
                )
            ).scalars().all()
        )
        clusters = list(
            db.execute(
                select(LiteratureCluster).where(
                    LiteratureCluster.project_id == project_id,
                    LiteratureCluster.status == "completed",
                )
            ).scalars().all()
        )
        items = list(
            db.execute(
                select(ProjectLiteratureItem).where(
                    ProjectLiteratureItem.project_id == project_id,
                    ProjectLiteratureItem.screening_status.in_(
                        ("included", "candidate")
                    ),
                )
            ).scalars().all()
        )
        if items:
            src_ids = [it.source_id for it in items]
            src_rows = db.execute(
                select(Source).where(Source.id.in_(src_ids))
            ).scalars().all()
            sources_by_id = {s.id: s for s in src_rows}
        included = sum(
            1 for it in items if it.screening_status == "included"
        )
        candidates = sum(
            1 for it in items if it.screening_status == "candidate"
        )

    return {
        "project": project,
        "classification": classification,
        "literature_run": run,
        "gaps": gaps,
        "clusters": clusters,
        "items": items,
        "sources_by_id": sources_by_id,
        "included_count": included,
        "candidate_count": candidates,
    }


def _taxonomy_signature(
    db: Session, cls: ProjectClassification | None
) -> str:
    if cls is None:
        return "none"
    parts: list[str] = []
    if cls.paper_type_code:
        pt = db.execute(
            select(PaperTypeRow).where(
                PaperTypeRow.code == cls.paper_type_code
            )
        ).scalar_one_or_none()
        if pt is not None:
            parts.append(f"pt:{pt.code}:{pt.taxonomy_version or '-'}")
    if cls.research_design_code:
        rd = db.execute(
            select(ResearchDesignRow).where(
                ResearchDesignRow.code == cls.research_design_code
            )
        ).scalar_one_or_none()
        if rd is not None:
            parts.append(f"rd:{rd.code}:{rd.taxonomy_version or '-'}")
    return "|".join(parts) if parts else "empty"


def compute_research_planning_hash(
    db: Session, *, project_id: uuid.UUID
) -> str:
    snap = build_research_planning_context(db, project_id=project_id)
    project = snap["project"]
    cls = snap["classification"]
    run = snap["literature_run"]

    parts = [
        f"plan_version:{RESEARCH_PLAN_VERSION}",
        f"template_version:{RESEARCH_PLAN_TEMPLATE_VERSION}",
        f"coverage_model:{RESEARCH_PLAN_COVERAGE_MODEL_VERSION}",
        f"ref_year:{RESEARCH_PLAN_REFERENCE_YEAR}",
        f"project:{project_id}",
    ]

    if project is not None:
        parts.append(
            "intent:"
            + _json(
                {
                    "objective": project.research_objective,
                    "questions": project.research_questions or [],
                    "hypotheses": project.hypotheses or [],
                    "scope": project.scope,
                    "constraints": project.constraints,
                }
            )
        )
    else:
        parts.append("intent:none")

    if cls is None:
        parts.append("classification:none")
    else:
        parts.append(
            "classification:"
            f"{cls.domain_id or '-'}:"
            f"{cls.paper_type_code or '-'}:"
            f"{cls.research_design_code or '-'}:"
            f"{cls.status}:"
            f"{cls.classifier_version or '-'}:"
            f"{cls.taxonomy_version or '-'}"
        )
        parts.append(f"taxonomy:{_taxonomy_signature(db, cls)}")

    if run is None:
        parts.append("literature_run:none")
    else:
        parts.append(
            f"literature_run:{run.id}:{run.context_hash or '-'}:"
            f"{run.analysis_version}"
        )
        parts.append(
            f"corpus:included={snap['included_count']}:"
            f"candidate={snap['candidate_count']}:"
            f"clusters={len(snap['clusters'])}:gaps={len(snap['gaps'])}"
        )
        for g in sorted(snap["gaps"], key=lambda x: (x.gap_type, x.id)):
            parts.append(
                f"gap:{g.gap_type}:{g.fingerprint or g.id}:"
                f"{g.confidence}:{g.status}"
            )
        for c in sorted(
            snap["clusters"], key=lambda x: (x.cluster_version, x.id)
        ):
            parts.append(
                f"cluster:{c.cluster_version}:{c.id}:{c.source_count}"
            )

        for it in sorted(snap["items"], key=lambda x: x.id):
            src = snap["sources_by_id"].get(it.source_id)
            src_year = getattr(src, "year", None) if src else None
            src_status = getattr(src, "status", None) if src else None
            src_chash = getattr(src, "content_hash", None) if src else None
            src_extracted = (
                getattr(src, "extracted_at", None) if src else None
            )
            parts.append(
                f"item:{it.id}:"
                f"src={it.source_id}:"
                f"screen={it.screening_status}:"
                f"mo={int(bool(it.manual_override))}:"
                f"pt={it.paper_type_code or '-'}:"
                f"rd={it.research_design_code or '-'}:"
                f"rel="
                f"{it.relevance_score if it.relevance_score is not None else '-'}:"
                f"yr={src_year if src_year is not None else '-'}:"
                f"sstatus={src_status or '-'}:"
                f"schash={src_chash or '-'}:"
                f"sext="
                f"{src_extracted.isoformat() if src_extracted else '-'}"
            )

    return _sha256(parts)
