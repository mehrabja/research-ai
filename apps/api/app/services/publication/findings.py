"""M33 — Compliance finding dataclass."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ComplianceFinding:
    rule_id: str
    category: str
    severity: str
    title: str
    message: str
    location: dict | None = None
    evidence: dict | None = None
    remediation: dict | None = None
    meta: dict | None = None


__all__ = ["ComplianceFinding"]
