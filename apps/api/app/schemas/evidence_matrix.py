"""Claim-centric evidence matrix schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class EvidenceClaimCreate(BaseModel):
    citation_run_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    manuscript_section_id: uuid.UUID | None = None
    claim_text: str = Field(..., min_length=1, max_length=10000)
    claim_type: str = Field(default="factual", min_length=1, max_length=64)
    location: dict[str, Any] | None = None


class EvidenceClaimRead(BaseModel):
    id: uuid.UUID
    citation_run_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    manuscript_section_id: uuid.UUID | None
    claim_hash: str
    claim_text: str
    claim_type: str
    location: dict[str, Any] | None
    claim_meta: dict[str, Any] | None
    status: str
    created_at: datetime


class EvidenceLinkCreate(BaseModel):
    evidence_type: str = Field(..., min_length=1, max_length=64)
    evidence_id: uuid.UUID
    source_id: uuid.UUID | None = None
    support_level: str = Field(..., min_length=1, max_length=64)
    relevance_score: Decimal = Field(default=0, ge=0, le=1)
    provenance: dict[str, Any] = Field(default_factory=dict)


class EvidenceLinkRead(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    evidence_type: str
    evidence_id: uuid.UUID
    source_id: uuid.UUID | None
    support_level: str
    relevance_score: Decimal
    provenance: dict[str, Any]
    created_at: datetime


class EvidenceMatrixItem(BaseModel):
    claim: EvidenceClaimRead
    evidence: list[EvidenceLinkRead]
