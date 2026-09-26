"""M39 claim-centric evidence matrix."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.db.models.citation import Claim, ClaimCitation, ClaimEvidence, CitationRun
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.evidence import EvidenceMatrixClaim, EvidenceMatrixCitation, EvidenceMatrixEvidence, EvidenceMatrixResponse
from app.services.reports import get_report

router=APIRouter(prefix="/reports",tags=["evidence"])

@router.get("/{report_id}/evidence/matrix",response_model=EvidenceMatrixResponse)
def get_evidence_matrix(report_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->EvidenceMatrixResponse:
    get_report(db,user_id=current_user.id,report_id=report_id)
    run=db.execute(select(CitationRun).where(CitationRun.report_id==report_id,CitationRun.status=="completed").order_by(CitationRun.created_at.desc(),CitationRun.id.desc()).limit(1)).scalar_one_or_none()
    if run is None:
        return EvidenceMatrixResponse(report_id=report_id,citation_run_id=uuid.uuid4(),manuscript_version_id=uuid.uuid4(),coverage_score=0.0,unsupported_count=0,claims=[])
    claims=list(db.execute(select(Claim).where(Claim.citation_run_id==run.id).order_by(Claim.created_at.asc())).scalars().all())
    out=[]
    for claim in claims:
        ev_rows=list(db.execute(select(ClaimEvidence).where(ClaimEvidence.claim_id==claim.id).order_by(ClaimEvidence.relevance_score.desc(),ClaimEvidence.id.asc())).scalars().all())
        cc_rows=list(db.execute(select(ClaimCitation).where(ClaimCitation.claim_id==claim.id).order_by(ClaimCitation.citation_order.asc().nullslast(),ClaimCitation.id.asc())).scalars().all())
        out.append(EvidenceMatrixClaim(
            id=claim.id,manuscript_section_id=claim.manuscript_section_id,claim_text=claim.claim_text,claim_type=claim.claim_type,status=claim.status,
            evidence=[EvidenceMatrixEvidence(id=e.id,evidence_type=e.evidence_type,evidence_id=e.evidence_id,source_id=e.source_id,support_level=e.support_level,relevance_score=float(e.relevance_score),provenance=e.provenance) for e in ev_rows],
            citations=[EvidenceMatrixCitation(id=x.id,citation_id=x.citation_id,relation_type=x.relation_type,support_level=x.support_level,relevance_score=float(x.relevance_score),citation_order=x.citation_order,paragraph_index=x.paragraph_index,sentence_index=x.sentence_index) for x in cc_rows],
        ))
    return EvidenceMatrixResponse(report_id=report_id,citation_run_id=run.id,manuscript_version_id=run.manuscript_version_id,coverage_score=float(run.coverage_score),unsupported_count=run.unsupported_count,claims=out)
