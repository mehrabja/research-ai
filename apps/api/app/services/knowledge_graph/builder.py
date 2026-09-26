"""M25 — Knowledge graph builder."""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    KnowledgeGraphConfigurationInvalid,
    KnowledgeGraphGenerationFailed,
    KnowledgeGraphInvalid,
)
from app.db.models.knowledge_graph import (
    KnowledgeGraphBuildRun,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphVersion,
)
from app.db.models.literature import (
    LiteratureCluster,
    LiteratureClusterMember,
    LiteratureGap,
    ProjectLiteratureItem,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report, ReportVersion
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanSection,
)
from app.db.models.source import Chunk, Source
from app.domain.knowledge_graph import (
    KNOWLEDGE_GRAPH_MODEL_VERSION,
    KNOWLEDGE_GRAPH_VERSION,
    KnowledgeGraphVersionStatus,
    edge_key,
    node_key,
)
from app.domain.knowledge_graph import (
    KnowledgeGraphNodeType as NT,
)
from app.domain.knowledge_graph import (
    KnowledgeGraphProvenanceType as PT,
)
from app.domain.knowledge_graph import (
    KnowledgeGraphRelationType as RT,
)
from app.services.knowledge_graph import context as ctx_svc
from app.services.knowledge_graph import validation as val_svc
from app.services.projects import get_project

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    graph_version: KnowledgeGraphVersion | None
    run: KnowledgeGraphBuildRun
    skipped: bool
    node_count: int
    edge_count: int


def _lock_project(db: Session, *, project_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"kg:{project_id}"},
    )


def _emit_event(
    db: Session, *, project_id: uuid.UUID,
    user_id: uuid.UUID | None, event_type: str,
    meta: dict[str, Any],
) -> None:
    db.add(ProjectEvent(
        project_id=project_id,
        user_id=user_id,
        event_type=event_type,
        event_meta=meta,
    ))


def record_skipped_run(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    context_hash: str,
    graph_version_id: uuid.UUID | None,
    reason: str,
    duration_ms: int,
) -> KnowledgeGraphBuildRun:
    run = KnowledgeGraphBuildRun(
        project_id=project_id,
        graph_version_id=graph_version_id,
        context_hash=context_hash,
        graph_version=KNOWLEDGE_GRAPH_VERSION,
        status="skipped",
        node_count=0,
        edge_count=0,
        duration_ms=duration_ms,
        error_message=None,
        output_summary={"reason": reason},
    )
    db.add(run)
    _emit_event(
        db, project_id=project_id, user_id=user_id,
        event_type="knowledge_graph_generation_skipped",
        meta={
            "context_hash": context_hash,
            "graph_version": KNOWLEDGE_GRAPH_VERSION,
            "reason": reason,
            "duration_ms": duration_ms,
        },
    )
    return run


def _next_version(db: Session, *, project_id: uuid.UUID) -> int:
    cur = db.execute(
        select(
            func.coalesce(func.max(KnowledgeGraphVersion.version), 0)
        ).where(KnowledgeGraphVersion.project_id == project_id)
    ).scalar_one()
    return int(cur) + 1


def _add_node(
    nodes: list[dict], node_type: str, entity_id: uuid.UUID,
    project_id: uuid.UUID, label: str | None = None,
) -> None:
    nodes.append({
        "node_key": node_key(node_type, str(entity_id)),
        "node_type": node_type,
        "entity_id": entity_id,
        "project_id": project_id,
        "label": label,
    })


def _add_edge(
    edges: list[dict], *,
    source_key: str, target_key: str,
    relation_type: str, provenance_type: str,
    project_id: uuid.UUID, provenance_ref: str | None = None,
) -> None:
    edges.append({
        "edge_key": edge_key(
            source_key, target_key, relation_type,
            provenance_type, provenance_ref,
        ),
        "source_key": source_key,
        "target_key": target_key,
        "relation_type": relation_type,
        "provenance_type": provenance_type,
        "provenance_ref": provenance_ref,
        "project_id": str(project_id),
    })


def _collect_nodes_edges(
    db: Session, *, project_id: uuid.UUID,
    plan: ResearchPlan | None,
) -> tuple[list[dict], list[dict]]:
    nodes: list[dict] = []
    edges: list[dict] = []

    project_row = db.get(Project, project_id)
    if project_row is not None:
        _add_node(
            nodes, NT.PROJECT.value, project_id, project_id,
            label=project_row.name,
        )

    report_rows = list(db.execute(
        select(Report).where(Report.project_id == project_id)
    ).scalars().all())
    report_ids: list[uuid.UUID] = []
    for report_row in report_rows:
        report_ids.append(report_row.id)
        _add_node(
            nodes, NT.REPORT.value, report_row.id, project_id,
            report_row.topic,
        )
        _add_edge(
            edges,
            source_key=node_key(NT.PROJECT.value, str(project_id)),
            target_key=node_key(NT.REPORT.value, str(report_row.id)),
            relation_type=RT.PROJECT_CONTAINS_REPORT.value,
            provenance_type=PT.DATABASE.value,
            project_id=project_id,
        )

    if report_ids:
        version_rows = list(db.execute(
            select(ReportVersion).where(
                ReportVersion.report_id.in_(report_ids)
            )
        ).scalars().all())
    else:
        version_rows = []
    for version_row in version_rows:
        _add_node(
            nodes, NT.REPORT_VERSION.value, version_row.id, project_id,
            label=f"v{version_row.version_number}",
        )
        _add_edge(
            edges,
            source_key=node_key(
                NT.REPORT.value, str(version_row.report_id)
            ),
            target_key=node_key(
                NT.REPORT_VERSION.value, str(version_row.id)
            ),
            relation_type=RT.REPORT_HAS_VERSION.value,
            provenance_type=PT.DATABASE.value,
            project_id=project_id,
        )

    if report_ids:
        source_rows = list(db.execute(
            select(Source).where(Source.report_id.in_(report_ids))
        ).scalars().all())
    else:
        source_rows = []
    source_ids: list[uuid.UUID] = []
    for source_row in source_rows:
        source_ids.append(source_row.id)
        _add_node(
            nodes, NT.SOURCE.value, source_row.id, project_id,
            source_row.title,
        )
        _add_edge(
            edges,
            source_key=node_key(
                NT.REPORT.value, str(source_row.report_id)
            ),
            target_key=node_key(NT.SOURCE.value, str(source_row.id)),
            relation_type=RT.REPORT_USES_SOURCE.value,
            provenance_type=PT.DATABASE.value,
            project_id=project_id,
        )

    if source_ids:
        chunk_rows = list(db.execute(
            select(Chunk).where(Chunk.source_id.in_(source_ids))
        ).scalars().all())
    else:
        chunk_rows = []
    for chunk_row in chunk_rows:
        _add_node(
            nodes, NT.CHUNK.value, chunk_row.id, project_id, label=None,
        )
        _add_edge(
            edges,
            source_key=node_key(
                NT.SOURCE.value, str(chunk_row.source_id)
            ),
            target_key=node_key(NT.CHUNK.value, str(chunk_row.id)),
            relation_type=RT.SOURCE_CONTAINS_CHUNK.value,
            provenance_type=PT.SOURCE_CHUNK.value,
            project_id=project_id,
        )

    lit_items = list(db.execute(
        select(ProjectLiteratureItem).where(
            ProjectLiteratureItem.project_id == project_id
        )
    ).scalars().all())
    for lit_row in lit_items:
        _add_node(
            nodes, NT.LITERATURE_ITEM.value, lit_row.id, project_id,
            label=None,
        )
        if lit_row.source_id in source_ids:
            _add_edge(
                edges,
                source_key=node_key(
                    NT.LITERATURE_ITEM.value, str(lit_row.id)
                ),
                target_key=node_key(
                    NT.SOURCE.value, str(lit_row.source_id)
                ),
                relation_type=(
                    RT.LITERATURE_ITEM_REFERS_TO_SOURCE.value
                ),
                provenance_type=PT.LITERATURE_ANALYSIS.value,
                project_id=project_id,
            )

    cluster_rows = list(db.execute(
        select(LiteratureCluster).where(
            LiteratureCluster.project_id == project_id,
            LiteratureCluster.status == "completed",
        )
    ).scalars().all())
    cluster_ids = {c.id for c in cluster_rows}
    for cluster_row in cluster_rows:
        _add_node(
            nodes, NT.LITERATURE_CLUSTER.value, cluster_row.id,
            project_id, cluster_row.name,
        )

    if cluster_ids:
        member_rows = list(db.execute(
            select(LiteratureClusterMember).where(
                LiteratureClusterMember.cluster_id.in_(
                    list(cluster_ids)
                )
            )
        ).scalars().all())
        for member_row in member_rows:
            _add_edge(
                edges,
                source_key=node_key(
                    NT.LITERATURE_ITEM.value,
                    str(member_row.literature_item_id),
                ),
                target_key=node_key(
                    NT.LITERATURE_CLUSTER.value,
                    str(member_row.cluster_id),
                ),
                relation_type=(
                    RT.LITERATURE_ITEM_MEMBER_OF_CLUSTER.value
                ),
                provenance_type=PT.LITERATURE_ANALYSIS.value,
                project_id=project_id,
            )
            _add_edge(
                edges,
                source_key=node_key(
                    NT.LITERATURE_CLUSTER.value,
                    str(member_row.cluster_id),
                ),
                target_key=node_key(
                    NT.LITERATURE_ITEM.value,
                    str(member_row.literature_item_id),
                ),
                relation_type=(
                    RT.CLUSTER_CONTAINS_LITERATURE_ITEM.value
                ),
                provenance_type=PT.LITERATURE_ANALYSIS.value,
                project_id=project_id,
            )

    gap_rows = list(db.execute(
        select(LiteratureGap).where(
            LiteratureGap.project_id == project_id,
        )
    ).scalars().all())
    for gap_row in gap_rows:
        _add_node(
            nodes, NT.LITERATURE_GAP.value, gap_row.id, project_id,
            gap_row.title,
        )
        for cid_str in (gap_row.supporting_cluster_ids or []):
            try:
                cid = uuid.UUID(str(cid_str))
            except (ValueError, TypeError):
                continue
            if cid not in cluster_ids:
                continue
            _add_edge(
                edges,
                source_key=node_key(
                    NT.LITERATURE_GAP.value, str(gap_row.id)
                ),
                target_key=node_key(
                    NT.LITERATURE_CLUSTER.value, str(cid)
                ),
                relation_type=RT.GAP_DETECTED_FROM_CLUSTER.value,
                provenance_type=PT.LITERATURE_ANALYSIS.value,
                project_id=project_id,
            )

    if plan is not None:
        _add_node(
            nodes, NT.RESEARCH_PLAN.value, plan.id, project_id,
            label=f"plan v{plan.version}",
        )
        section_rows = list(db.execute(
            select(ResearchPlanSection)
            .where(ResearchPlanSection.plan_id == plan.id)
            .order_by(ResearchPlanSection.display_order.asc())
        ).scalars().all())
        for section_row in section_rows:
            _add_node(
                nodes, NT.RESEARCH_PLAN_SECTION.value, section_row.id,
                project_id, section_row.title,
            )
            _add_edge(
                edges,
                source_key=node_key(
                    NT.RESEARCH_PLAN.value, str(plan.id)
                ),
                target_key=node_key(
                    NT.RESEARCH_PLAN_SECTION.value, str(section_row.id)
                ),
                relation_type=RT.PLAN_CONTAINS_SECTION.value,
                provenance_type=PT.RESEARCH_PLAN.value,
                project_id=project_id,
            )

        req_rows = list(db.execute(
            select(ResearchEvidenceRequirement)
            .where(ResearchEvidenceRequirement.plan_id == plan.id)
        ).scalars().all())
        for req_row in req_rows:
            _add_node(
                nodes, NT.EVIDENCE_REQUIREMENT.value, req_row.id,
                project_id, req_row.requirement_key,
            )
            _add_edge(
                edges,
                source_key=node_key(
                    NT.RESEARCH_PLAN_SECTION.value,
                    str(req_row.section_id),
                ),
                target_key=node_key(
                    NT.EVIDENCE_REQUIREMENT.value, str(req_row.id)
                ),
                relation_type=RT.SECTION_REQUIRES_EVIDENCE.value,
                provenance_type=PT.RESEARCH_PLAN.value,
                project_id=project_id,
            )

    dedup_nodes: dict[str, dict] = {}
    for n in nodes:
        dedup_nodes.setdefault(n["node_key"], n)
    dedup_edges: dict[str, dict] = {}
    for e in edges:
        dedup_edges.setdefault(e["edge_key"], e)
    return list(dedup_nodes.values()), list(dedup_edges.values())


def _reactivate_or_skip(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    existing: KnowledgeGraphBuildRun,
    context_hash: str,
    force: bool,
    duration_ms: int,
) -> BuildResult:
    gv = (
        db.get(KnowledgeGraphVersion, existing.graph_version_id)
        if existing.graph_version_id else None
    )

    if gv is not None and gv.status == "superseded":
        prev_active = ctx_svc.active_graph_version(
            db, project_id=project_id
        )
        if prev_active is not None and prev_active.id != gv.id:
            prev_active.status = (
                KnowledgeGraphVersionStatus.SUPERSEDED.value
            )
            db.flush()
        gv.status = KnowledgeGraphVersionStatus.READY.value
        db.flush()
        reason = "reactivated_superseded"
    else:
        reason = (
            "force_ignored_duplicate" if force
            else "context_unchanged"
        )

    run = KnowledgeGraphBuildRun(
        project_id=project_id,
        graph_version_id=existing.graph_version_id,
        context_hash=context_hash,
        graph_version=KNOWLEDGE_GRAPH_VERSION,
        status="skipped",
        node_count=existing.node_count,
        edge_count=existing.edge_count,
        duration_ms=duration_ms,
        output_summary={"reason": reason},
    )
    db.add(run)
    _emit_event(
        db, project_id=project_id, user_id=user_id,
        event_type="knowledge_graph_generation_skipped",
        meta={
            "context_hash": context_hash,
            "graph_version": KNOWLEDGE_GRAPH_VERSION,
            "force": bool(force),
            "reason": reason,
            "graph_version_id": (
                str(existing.graph_version_id)
                if existing.graph_version_id else None
            ),
            "duration_ms": duration_ms,
        },
    )
    return BuildResult(
        graph_version=gv,
        run=run,
        skipped=True,
        node_count=existing.node_count,
        edge_count=existing.edge_count,
    )


def build_knowledge_graph(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    force: bool = False,
    commit: bool = True,
) -> BuildResult:
    settings = get_settings()
    if not settings.knowledge_graph_enabled:
        raise KnowledgeGraphConfigurationInvalid(
            "knowledge graph is disabled"
        )

    started = time.perf_counter()
    context_hash: str | None = None

    project_row = get_project(
        db, user_id=user_id, project_id=project_id
    )
    if project_row.status == "archived":
        raise KnowledgeGraphGenerationFailed("project is archived")

    try:
        _lock_project(db, project_id=project_id)
        context_hash = ctx_svc.compute_graph_context_hash(
            db, project_id=project_id
        )

        existing = ctx_svc.completed_build_run_exists(
            db, project_id=project_id, context_hash=context_hash
        )
        if existing is not None:
            duration_ms = int((time.perf_counter() - started) * 1000)
            result = _reactivate_or_skip(
                db,
                project_id=project_id,
                user_id=user_id,
                existing=existing,
                context_hash=context_hash,
                force=force,
                duration_ms=duration_ms,
            )
            if commit:
                db.commit()
                if result.run is not None:
                    db.refresh(result.run)
                if result.graph_version is not None:
                    db.refresh(result.graph_version)
            else:
                db.flush()
            return result

        _emit_event(
            db, project_id=project_id, user_id=user_id,
            event_type="knowledge_graph_generation_started",
            meta={
                "context_hash": context_hash,
                "graph_version": KNOWLEDGE_GRAPH_VERSION,
            },
        )

        plan = ctx_svc.get_latest_ready_plan(db, project_id=project_id)
        lit_run = ctx_svc.get_latest_completed_literature_run(
            db, project_id=project_id
        )

        nodes, edges = _collect_nodes_edges(
            db, project_id=project_id, plan=plan
        )
        vres = val_svc.validate_graph_structure(
            nodes=nodes, edges=edges, project_id=str(project_id)
        )
        if not vres.valid():
            raise KnowledgeGraphInvalid(
                "invalid graph: " + "; ".join(vres.errors)
            )

        next_version = _next_version(db, project_id=project_id)
        prev_active = ctx_svc.active_graph_version(
            db, project_id=project_id
        )

        gv = KnowledgeGraphVersion(
            project_id=project_id,
            version=next_version,
            status=KnowledgeGraphVersionStatus.BUILDING.value,
            graph_version=KNOWLEDGE_GRAPH_VERSION,
            context_hash=context_hash,
            source_literature_run_id=(
                lit_run.id if lit_run is not None else None
            ),
            research_plan_id=plan.id if plan is not None else None,
            node_count=len(nodes),
            edge_count=len(edges),
            graph_meta={
                "model_version": KNOWLEDGE_GRAPH_MODEL_VERSION,
                "validation_score": vres.score,
                "warnings": vres.warnings,
                "max_traversal_depth": (
                    settings.knowledge_graph_max_traversal_depth
                ),
            },
            created_by=user_id,
        )
        db.add(gv)
        db.flush()

        node_owner: dict[str, tuple[uuid.UUID, uuid.UUID]] = {}
        node_id_by_key: dict[str, uuid.UUID] = {}
        for n in nodes:
            row = KnowledgeGraphNode(
                graph_version_id=gv.id,
                project_id=project_id,
                node_type=n["node_type"],
                node_key=n["node_key"],
                entity_id=n["entity_id"],
                label=n.get("label"),
                node_meta=None,
            )
            db.add(row)
            db.flush()
            node_id_by_key[n["node_key"]] = row.id
            node_owner[n["node_key"]] = (
                row.project_id, row.graph_version_id
            )

        pv = val_svc.validate_persisted_edges(
            node_owner=node_owner,
            edges=edges,
            project_id=project_id,
            graph_version_id=gv.id,
        )
        if not pv.valid():
            raise KnowledgeGraphInvalid(
                "invalid graph edges: " + "; ".join(pv.errors)
            )

        for e in edges:
            db.add(KnowledgeGraphEdge(
                graph_version_id=gv.id,
                project_id=project_id,
                source_node_id=node_id_by_key[e["source_key"]],
                target_node_id=node_id_by_key[e["target_key"]],
                relation_type=e["relation_type"],
                provenance_type=e["provenance_type"],
                provenance_ref=e.get("provenance_ref"),
                confidence=None,
                weight=1,
                edge_key=e["edge_key"],
                edge_meta=None,
            ))

        if prev_active is not None:
            prev_active.status = (
                KnowledgeGraphVersionStatus.SUPERSEDED.value
            )
            db.flush()

        gv.status = KnowledgeGraphVersionStatus.READY.value
        db.flush()

        duration_ms = int((time.perf_counter() - started) * 1000)
        run = KnowledgeGraphBuildRun(
            project_id=project_id,
            graph_version_id=gv.id,
            context_hash=context_hash,
            graph_version=KNOWLEDGE_GRAPH_VERSION,
            status="completed",
            node_count=len(nodes),
            edge_count=len(edges),
            duration_ms=duration_ms,
            input_snapshot={
                "model_version": KNOWLEDGE_GRAPH_MODEL_VERSION,
                "literature_run_id": (
                    str(lit_run.id) if lit_run is not None else None
                ),
                "research_plan_id": (
                    str(plan.id) if plan is not None else None
                ),
            },
            output_summary={
                "version": next_version,
                "nodes": len(nodes),
                "edges": len(edges),
                "validation_score": vres.score,
            },
        )
        db.add(run)
        db.flush()

        _emit_event(
            db, project_id=project_id, user_id=user_id,
            event_type="knowledge_graph_generation_completed",
            meta={
                "graph_version_id": str(gv.id),
                "context_hash": context_hash,
                "graph_version": KNOWLEDGE_GRAPH_VERSION,
                "node_count": len(nodes),
                "edge_count": len(edges),
                "duration_ms": duration_ms,
            },
        )

        if commit:
            db.commit()
            db.refresh(gv)
            db.refresh(run)
        else:
            db.flush()
        return BuildResult(
            graph_version=gv, run=run, skipped=False,
            node_count=len(nodes), edge_count=len(edges),
        )

    except Exception as exc:
        logger.exception("knowledge_graph_generation_failed")
        duration_ms = int((time.perf_counter() - started) * 1000)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            logger.exception("kg_rollback_failed")
        try:
            db.add(KnowledgeGraphBuildRun(
                project_id=project_id,
                graph_version_id=None,
                context_hash=context_hash or "-",
                graph_version=KNOWLEDGE_GRAPH_VERSION,
                status="failed",
                node_count=0,
                edge_count=0,
                duration_ms=duration_ms,
                error_message=str(exc)[:500],
            ))
            _emit_event(
                db, project_id=project_id, user_id=user_id,
                event_type="knowledge_graph_generation_failed",
                meta={
                    "context_hash": context_hash or "-",
                    "graph_version": KNOWLEDGE_GRAPH_VERSION,
                    "error": str(exc)[:200],
                    "duration_ms": duration_ms,
                },
            )
            if commit:
                db.commit()
        except Exception:
            logger.exception("kg_failure_persist_failed")
            if commit:
                db.rollback()
        raise
