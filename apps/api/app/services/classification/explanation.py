"""M22 — Classification explanation builder.

Turns an ``EvidenceCollector`` into a stable JSON structure that
captures *why* each dimension was chosen. Persisted with each
``ClassificationRun`` for audit and UI display.
"""
from __future__ import annotations

from typing import Any

from app.services.classification.evidence import EvidenceCollector


def _explain_target(
    collector: EvidenceCollector,
    *,
    target: str,
    selected_code: str | None,
) -> dict[str, Any]:
    items = collector.items_for(target)
    supporting = (
        [i for i in items if i.target_code == selected_code]
        if selected_code
        else []
    )

    return {
        "selected": selected_code,
        "evidence_count": len(supporting),
        "evidence": [
            {
                "signal_type": e.signal_type,
                "source_location": e.source_location,
                "matched_text": e.matched_text,
                "weight": round(float(e.weight), 4),
                "target_code": e.target_code,
            }
            for e in supporting
        ],
    }


def _collect_warnings(
    *,
    domain_code: str | None,
    paper_type_code: str | None,
    research_design_code: str | None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    if domain_code is None:
        warnings.append(
            {
                "code": "domain_missing",
                "message": "No domain signal matched the taxonomy",
            }
        )
    if paper_type_code in (None, "unknown"):
        warnings.append(
            {
                "code": "paper_type_unknown",
                "message": "Paper type could not be determined",
            }
        )
    if research_design_code in (None, "unknown"):
        warnings.append(
            {
                "code": "research_design_unknown",
                "message": "Research design could not be determined",
            }
        )

    return warnings


def build_classification_explanation(
    *,
    collector: EvidenceCollector,
    domain_code: str | None,
    paper_type_code: str | None,
    research_design_code: str | None,
) -> dict[str, Any]:
    """Build the explanation JSON for a single classification run."""
    return {
        "domain": _explain_target(
            collector, target="domain", selected_code=domain_code
        ),
        "paper_type": _explain_target(
            collector,
            target="paper_type",
            selected_code=paper_type_code,
        ),
        "research_design": _explain_target(
            collector,
            target="research_design",
            selected_code=research_design_code,
        ),
        "warnings": _collect_warnings(
            domain_code=domain_code,
            paper_type_code=paper_type_code,
            research_design_code=research_design_code,
        ),
    }
