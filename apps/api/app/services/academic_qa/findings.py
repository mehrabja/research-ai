"""M31 — QA finding dataclass."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.domain.academic_qa import QAClassification


@dataclass
class QAFinding:
    rule_id: str
    category: str
    severity: str
    title: str
    message: str
    classification: str = QAClassification.DETERMINISTIC.value
    confidence: float | None = None
    manuscript_section_id: uuid.UUID | None = None
    claim_id: uuid.UUID | None = None
    citation_id: uuid.UUID | None = None
    location: dict | None = None
    evidence: dict | None = None
    remediation: dict | None = None
    meta: dict | None = field(default=None)


__all__ = ["QAFinding"]
