"""M39 evidence matrix API schema."""
from __future__ import annotations
import uuid
from pydantic import BaseModel, ConfigDict

class EvidenceMatrixEvidence(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: uuid.UUID
    evidence_type: str
    evidence_id: uuid.UUID
    source_id: uuid.UUID | None
    support_level: str
    relevance_score: float
    provenance: dict

class EvidenceMatrixCitation(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: uuid.UUID
    citation_id: uuid.UUID
    relation_type: str
    support_level: str
    relevance_score: float
    citation_order: int | None
    paragraph_index: int | None
    sentence_index: int | None

class EvidenceMatrixClaim(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: uuid.UUID
    manuscript_section_id: uuid.UUID | None
    claim_text: str
    claim_type: str
    status: str
    evidence: list[EvidenceMatrixEvidence]
    citations: list[EvidenceMatrixCitation]

class EvidenceMatrixResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    report_id: uuid.UUID
    citation_run_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    coverage_score: float
    unsupported_count: int
    claims: list[EvidenceMatrixClaim]
