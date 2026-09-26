"""M25 — Deterministic graph context hash."""
from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.knowledge_graph import (
    KnowledgeGraphBuildRun,
    KnowledgeGraphVersion,
)
from app.db.models.literature import (
    LiteratureCluster,
    LiteratureClusterMember,
    LiteratureGap,
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.project import Project
from app.db.models.report import Report, ReportVersion
from app.db.models.research_plan import ResearchPlan, ResearchPlanSection
from app.db.models.source import Chunk, Source
from app.domain.knowledge_graph import (
    KNOWLEDGE_GRAPH_MODEL_VERSION,
    KNOWLEDGE_GRAPH_VERSION,
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


def get_latest_completed_literature_run(
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


def get_latest_ready_plan(
    db: Session, *, project_id: uuid.UUID
) -> ResearchPlan | None:
    return db.execute(
        select(ResearchPlan)
        .where(
            ResearchPlan.project_id == project_id,
            ResearchPlan.status == "ready",
        )
        .order_by(ResearchPlan.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def compute_graph_context_hash(
    db: Session, *, project_id: uuid.UUID
) -> str:
    parts: list[str] = [
        f"model:{KNOWLEDGE_GRAPH_MODEL_VERSION}",
        f"graph:{KNOWLEDGE_GRAPH_VERSION}",
        f"project:{project_id}",
    ]

    project = db.get(Project, project_id)
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

    run = get_latest_completed_literature_run(db, project_id=project_id)
    if run is None:
        parts.append("lit_run:none")
    else:
        parts.append(
            f"lit_run:{run.id}:{run.context_hash or '-'}:"
            f"{run.analysis_version}"
        )

    plan = get_latest_ready_plan(db, project_id=project_id)
    if plan is None:
        parts.append("plan:none")
    else:
        parts.append(
            f"plan:{plan.id}:{plan.version}:{plan.planner_version}:"
            f"{plan.context_hash}"
        )

    reports = list(db.execute(
        select(Report.id, Report.topic)
        .where(Report.project_id == project_id)
        .order_by(Report.id.asc())
    ).all())
    for rid, topic in reports:
        parts.append(f"report:{rid}:topic={topic or '-'}")

    report_ids: list[uuid.UUID] = [r[0] for r in reports]

    if report_ids:
        version_rows = db.execute(
            select(
                ReportVersion.id,
                ReportVersion.report_id,
                ReportVersion.version_number,
            )
            .where(ReportVersion.report_id.in_(report_ids))
            .order_by(ReportVersion.id.asc())
        ).all()
        for vid, rid, vnum in version_rows:
            parts.append(f"rver:{vid}:report={rid}:n={vnum}")
    else:
        parts.append("rver:none")

    source_ids: list[uuid.UUID] = []
    if report_ids:
        source_rows = db.execute(
            select(
                Source.id,
                Source.report_id,
                Source.status,
                Source.title,
                Source.year,
                Source.content_hash,
                Source.extracted_at,
            )
            .where(Source.report_id.in_(report_ids))
            .order_by(Source.id.asc())
        ).all()
        for sid, rid, status, title, year, chash, extracted in source_rows:
            source_ids.append(sid)
            parts.append(
                f"src:{sid}:report={rid}:status={status or '-'}:"
                f"title={title or '-'}:"
                f"year={year if year is not None else '-'}:"
                f"chash={chash or '-'}:"
                f"extracted={extracted.isoformat() if extracted else '-'}"
            )

    if source_ids:
        chunk_rows = db.execute(
            select(Chunk.id, Chunk.source_id, Chunk.chunk_index)
            .where(Chunk.source_id.in_(source_ids))
            .order_by(Chunk.id.asc())
        ).all()
        for cid, sid, idx in chunk_rows:
            parts.append(f"chunk:{cid}:src={sid}:idx={idx}")
    else:
        parts.append("chunks:none")

    # CitationLink intentionally excluded — global, not project-scoped.

    lit_items = db.execute(
        select(
            ProjectLiteratureItem.id,
            ProjectLiteratureItem.source_id,
            ProjectLiteratureItem.screening_status,
            ProjectLiteratureItem.manual_override,
            ProjectLiteratureItem.paper_type_code,
            ProjectLiteratureItem.research_design_code,
        )
        .where(ProjectLiteratureItem.project_id == project_id)
        .order_by(ProjectLiteratureItem.id.asc())
    ).all()
    for it in lit_items:
        parts.append(
            f"lit:{it.id}:src={it.source_id}:"
            f"screen={it.screening_status}:"
            f"mo={int(bool(it.manual_override))}:"
            f"pt={it.paper_type_code or '-'}:"
            f"rd={it.research_design_code or '-'}"
        )

    cluster_rows = db.execute(
        select(
            LiteratureCluster.id,
            LiteratureCluster.name,
            LiteratureCluster.cluster_version,
            LiteratureCluster.status,
        )
        .where(LiteratureCluster.project_id == project_id)
        .order_by(LiteratureCluster.id.asc())
    ).all()
    cluster_ids: list[uuid.UUID] = []
    for cid, cname, cver, cst in cluster_rows:
        cluster_ids.append(cid)
        parts.append(
            f"cluster:{cid}:{cver}:{cst}:name={cname or '-'}"
        )

    if cluster_ids:
        member_rows = db.execute(
            select(
                LiteratureClusterMember.cluster_id,
                LiteratureClusterMember.literature_item_id,
            )
            .where(LiteratureClusterMember.cluster_id.in_(cluster_ids))
            .order_by(LiteratureClusterMember.id.asc())
        ).all()
        for cid, lid in member_rows:
            parts.append(f"member:{cid}->{lid}")
    else:
        parts.append("member:none")

    gap_rows = db.execute(
        select(
            LiteratureGap.id,
            LiteratureGap.gap_type,
            LiteratureGap.status,
            LiteratureGap.fingerprint,
            LiteratureGap.title,
        )
        .where(LiteratureGap.project_id == project_id)
        .order_by(LiteratureGap.id.asc())
    ).all()
    for gid, gtype, gstat, gfp, gtitle in gap_rows:
        parts.append(
            f"gap:{gid}:{gtype}:{gstat}:{gfp or '-'}:"
            f"title={gtitle or '-'}"
        )

    if plan is not None:
        section_rows = db.execute(
            select(
                ResearchPlanSection.id,
                ResearchPlanSection.section_key,
                ResearchPlanSection.title,
                ResearchPlanSection.display_order,
            )
            .where(ResearchPlanSection.plan_id == plan.id)
            .order_by(ResearchPlanSection.id.asc())
        ).all()
        for sid, skey, stitle, order in section_rows:
            parts.append(
                f"section:{sid}:{skey}:{stitle or '-'}:order={order}"
            )

    return _sha256(parts)


def completed_build_run_exists(
    db: Session, *, project_id: uuid.UUID, context_hash: str
) -> KnowledgeGraphBuildRun | None:
    return db.execute(
        select(KnowledgeGraphBuildRun)
        .where(
            KnowledgeGraphBuildRun.project_id == project_id,
            KnowledgeGraphBuildRun.context_hash == context_hash,
            KnowledgeGraphBuildRun.graph_version
            == KNOWLEDGE_GRAPH_VERSION,
            KnowledgeGraphBuildRun.status == "completed",
        )
    ).scalar_one_or_none()


def active_graph_version(
    db: Session, *, project_id: uuid.UUID
) -> KnowledgeGraphVersion | None:
    return db.execute(
        select(KnowledgeGraphVersion)
        .where(
            KnowledgeGraphVersion.project_id == project_id,
            KnowledgeGraphVersion.status == "ready",
        )
        .order_by(KnowledgeGraphVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()
