"""Claim-centric evidence matrix routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.evidence_matrix import (
    EvidenceClaimCreate,
    EvidenceClaimRead,
    EvidenceLinkCreate,
    EvidenceLinkRead,
    EvidenceMatrixItem,
)
from app.services.evidence_matrix import (
    add_evidence,
    create_claim,
    list_matrix,
    remove_evidence,
)

router = APIRouter(prefix="/reports", tags=["evidence"])


@router.get(
    "/{report_id}/evidence-matrix",
    response_model=list[EvidenceMatrixItem],
)
def get_evidence_matrix(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EvidenceMatrixItem]:
    return [
        EvidenceMatrixItem(
            claim=EvidenceClaimRead.model_validate(claim),
            evidence=[
                EvidenceLinkRead.model_validate(link) for link in links
            ],
        )
        for claim, links in list_matrix(
            db,
            report_id=report_id,
            user_id=current_user.id,
        )
    ]


@router.post(
    "/{report_id}/evidence/claims",
    response_model=EvidenceClaimRead,
    status_code=status.HTTP_201_CREATED,
)
def create_evidence_claim(
    report_id: uuid.UUID,
    body: EvidenceClaimCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceClaimRead:
    row = create_claim(
        db,
        report_id=report_id,
        user_id=current_user.id,
        **body.model_dump(),
    )
    return EvidenceClaimRead.model_validate(row)


@router.post(
    "/{report_id}/evidence/claims/{claim_id}/links",
    response_model=EvidenceLinkRead,
    status_code=status.HTTP_201_CREATED,
)
def link_evidence(
    report_id: uuid.UUID,
    claim_id: uuid.UUID,
    body: EvidenceLinkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceLinkRead:
    row = add_evidence(
        db,
        report_id=report_id,
        user_id=current_user.id,
        claim_id=claim_id,
        **body.model_dump(),
    )
    return EvidenceLinkRead.model_validate(row)


@router.delete(
    "/{report_id}/evidence/claims/{claim_id}/links/{evidence_link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_evidence(
    report_id: uuid.UUID,
    claim_id: uuid.UUID,
    evidence_link_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    remove_evidence(
        db,
        report_id=report_id,
        user_id=current_user.id,
        claim_id=claim_id,
        evidence_link_id=evidence_link_id,
    )
