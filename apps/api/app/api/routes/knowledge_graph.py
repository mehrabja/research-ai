"""M25 — Knowledge graph routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import KnowledgeGraphConfigurationInvalid
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.knowledge_graph import (
    KnowledgeGraphBuildResponse,
    KnowledgeGraphGenerateRequest,
    KnowledgeGraphNeighborRead,
    KnowledgeGraphNodeRead,
    KnowledgeGraphNodeListResponse,
    KnowledgeGraphQueryRequest,
    KnowledgeGraphQueryResponse,
    KnowledgeGraphRead,
    KnowledgeGraphSummaryRead,
)
from app.services.knowledge_graph import builder as builder_svc
from app.services.knowledge_graph import export as export_svc
from app.services.knowledge_graph import jobs as jobs_svc
from app.services.knowledge_graph import queries as queries_svc
from app.services.projects import get_project

router = APIRouter(prefix="/projects", tags=["knowledge-graph"])


@router.post(
    "/{project_id}/knowledge-graph/generate",
    response_model=KnowledgeGraphBuildResponse,
)
def generate(
    project_id: uuid.UUID,
    body: KnowledgeGraphGenerateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeGraphBuildResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    settings = get_settings()

    if not settings.knowledge_graph_enabled:
        raise KnowledgeGraphConfigurationInvalid(
            "knowledge graph is disabled"
        )

    effective_async = (
        settings.knowledge_graph_async_jobs
        if body.async_ is None
        else body.async_
    )

    if effective_async:
        job_id = jobs_svc.enqueue_knowledge_graph(
            db,
            project_id=project_id,
            user_id=current_user.id,
            force=body.force,
        )
        if job_id is None:
            response.status_code = 500
            return KnowledgeGraphBuildResponse(
                status="failed", job_id=None, graph=None
            )
        response.status_code = 202
        return KnowledgeGraphBuildResponse(
            status="queued", job_id=job_id, graph=None
        )

    result = builder_svc.build_knowledge_graph(
        db,
        user_id=current_user.id,
        project_id=project_id,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    if result.graph_version is None:
        return KnowledgeGraphBuildResponse(
            status=result.run.status, job_id=None, graph=None
        )
    return KnowledgeGraphBuildResponse(
        status=result.run.status,
        job_id=None,
        graph=KnowledgeGraphRead.model_validate(result.graph_version),
    )


@router.get(
    "/{project_id}/knowledge-graph",
    response_model=KnowledgeGraphRead,
)
def get_graph(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeGraphRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    gv = queries_svc.get_graph(db, project_id=project_id)
    return KnowledgeGraphRead.model_validate(gv)


@router.get(
    "/{project_id}/knowledge-graph/summary",
    response_model=KnowledgeGraphSummaryRead,
)
def get_summary(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeGraphSummaryRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    return KnowledgeGraphSummaryRead.model_validate(
        queries_svc.get_graph_summary(db, project_id=project_id)
    )


@router.get(
    "/{project_id}/knowledge-graph/nodes",
    response_model=KnowledgeGraphNodeListResponse,
)
def list_nodes(
    project_id: uuid.UUID,
    search: str | None = Query(default=None, max_length=200),
    node_type: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeGraphNodeListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    rows, total = queries_svc.list_nodes(
        db,
        project_id=project_id,
        search=search,
        node_type=node_type,
        limit=limit,
        offset=offset,
    )
    return KnowledgeGraphNodeListResponse(
        items=[KnowledgeGraphNodeRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{project_id}/knowledge-graph/nodes/{node_id}",
    response_model=KnowledgeGraphNodeRead,
)
def get_node(
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeGraphNodeRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    node = queries_svc.get_node(
        db, project_id=project_id, node_id=node_id
    )
    return KnowledgeGraphNodeRead.model_validate(node)


@router.get(
    "/{project_id}/knowledge-graph/nodes/{node_id}/neighbors",
    response_model=list[KnowledgeGraphNeighborRead],
)
def get_neighbors(
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    direction: str = Query(default="both", pattern="^(in|out|both)$"),
    relation_types: list[str] | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=10_000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KnowledgeGraphNeighborRead]:
    get_project(db, user_id=current_user.id, project_id=project_id)
    rows = queries_svc.get_neighbors(
        db,
        project_id=project_id,
        node_id=node_id,
        relation_types=relation_types,
        direction=direction,
        limit=limit,
    )
    return [KnowledgeGraphNeighborRead.model_validate(r) for r in rows]


@router.post(
    "/{project_id}/knowledge-graph/query",
    response_model=KnowledgeGraphQueryResponse,
)
def run_query(
    project_id: uuid.UUID,
    body: KnowledgeGraphQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeGraphQueryResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    result = queries_svc.bounded_traversal(
        db,
        project_id=project_id,
        start_node_id=body.start_node_id,
        max_depth=body.max_depth,
        max_nodes=body.max_nodes,
        relation_types=body.relation_types,
    )
    return KnowledgeGraphQueryResponse.model_validate(result)


@router.get(
    "/{project_id}/knowledge-graph/export",
    summary="Export the active knowledge graph",
)
def export_graph(
    project_id: uuid.UUID,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    get_project(db, user_id=current_user.id, project_id=project_id)
    body, media_type = export_svc.export_graph(
        db,
        project_id=project_id,
        export_format=format,  # type: ignore[arg-type]
    )
    suffix = "json" if format == "json" else "csv"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="knowledge-graph-{project_id}.{suffix}"'
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
