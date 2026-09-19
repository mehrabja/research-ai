"""M21 — Classification routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.research_classification import (
    ClassificationEvidence,
)
from app.db.models.research_taxonomy import ResearchDomain
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.research_classification import (
    ClassificationOverride,
    ClassificationRead,
    EvidenceItemRead,
    EvidenceListResponse,
    _DomainSummary,
    _PaperTypeSummary,
    _ResearchDesignSummary,
)
from app.services.classification import orchestrator
from app.services.projects import get_project

router = APIRouter(prefix="/projects", tags=["classification"])


def _to_read(row, *, db: Session) -> ClassificationRead:
    domain_summary = _DomainSummary(
        code=None,
        name=None,
        confidence=row.domain_confidence,
        source=row.domain_source,
        method=row.domain_method,
        reason=row.domain_reason,
        alternatives=row.domain_alternatives or [],
    )
    if row.domain_id is not None:
        dom = db.get(ResearchDomain, row.domain_id)
        if dom is not None:
            domain_summary.code = dom.code
            domain_summary.name = dom.name

    return ClassificationRead(
        id=row.id,
        project_id=row.project_id,
        domain=domain_summary,
        paper_type=_PaperTypeSummary(
            code=row.paper_type_code,
            confidence=row.paper_type_confidence,
            source=row.paper_type_source,
            method=row.paper_type_method,
            reason=row.paper_type_reason,
            secondary=list(row.paper_type_secondary or []),
            alternatives=row.paper_type_alternatives or [],
        ),
        research_design=_ResearchDesignSummary(
            code=row.research_design_code,
            confidence=row.research_design_confidence,
            source=row.research_design_source,
            method=row.research_design_method,
            reason=row.research_design_reason,
            alternatives=row.research_design_alternatives or [],
        ),
        status=row.status,
        needs_review=row.needs_review,
        error_message=row.error_message,
        classifier_version=row.classifier_version,
        taxonomy_version=row.taxonomy_version,
        context_meta=row.context_meta,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get(
    "/{project_id}/classification",
    response_model=ClassificationRead,
    summary="Get the research classification for a project",
)
def get_classification(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassificationRead:
    get_project(db, user_id=current_user.id, project_id=project_id)
    row = orchestrator.get_or_create_classification(
        db, project_id=project_id, user_id=current_user.id
    )
    return _to_read(row, db=db)


@router.post(
    "/{project_id}/classification/recompute",
    response_model=ClassificationRead,
    summary="Recompute the classification for a project",
)
def recompute_classification(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassificationRead:
    row = orchestrator.recompute_project(
        db, user_id=current_user.id, project_id=project_id
    )
    return _to_read(row, db=db)


@router.patch(
    "/{project_id}/classification",
    response_model=ClassificationRead,
    summary="Override one or more classification fields",
)
def override_classification(
    project_id: uuid.UUID,
    body: ClassificationOverride,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassificationRead:
    updates = body.model_dump(exclude_unset=True)
    row = orchestrator.override_classification(
        db,
        user_id=current_user.id,
        project_id=project_id,
        updates=updates,
    )
    return _to_read(row, db=db)


@router.get(
    "/{project_id}/classification/evidence",
    response_model=EvidenceListResponse,
    summary="List classification evidence signals",
)
def list_evidence(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EvidenceListResponse:
    get_project(db, user_id=current_user.id, project_id=project_id)
    row = orchestrator.get_or_create_classification(
        db, project_id=project_id, user_id=current_user.id
    )
    base = select(ClassificationEvidence).where(
        ClassificationEvidence.classification_id == row.id
    )
    total = int(
        db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
    )
    rows = (
        db.execute(
            base.order_by(
                ClassificationEvidence.created_at.asc(),
                ClassificationEvidence.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return EvidenceListResponse(
        items=[EvidenceItemRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
