"""M35 — Deterministic planner.

Takes a goal + current state and produces an ordered node list.
No LLM is invoked here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.orchestration import ORCHESTRATION_PLANNER_VERSION


@dataclass
class PlannedNode:
    node_key: str
    sequence: int
    depends_on: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    strategy: str
    nodes: list[PlannedNode]

    def node_keys(self) -> list[str]:
        return [n.node_key for n in self.nodes]


_GOAL_PRESETS: dict[str, list[str]] = {
    "research_pipeline": [
        "build_plan",
        "manuscript_generate",
        "technical_intelligence",
        "manuscript_prose_generate",
        "generate_citations",
        "academic_qa",
        "humanize",
        "target_compliance",
    ],
    "complete_pre_submission": [
        "build_plan",
        "manuscript_generate",
        "technical_intelligence",
        "generate_citations",
        "academic_qa",
        "humanize",
        "target_compliance",
    ],
    "prepare_for_submission": [
        "generate_citations",
        "academic_qa",
        "target_compliance",
    ],
    "resolve_qa_blockers": [
        "academic_qa",
        "humanize",
    ],
    "improve_citation_completeness": [
        "technical_intelligence",
        "generate_citations",
    ],
    "reviewer_revision_plan": [
        "academic_qa",
    ],
    "roundtable_review": [
        "roundtable_review",
    ],
}


def plan_orchestration(
    *,
    goal: str,
    strategy: str,
    payload: dict[str, Any] | None = None,
    max_nodes: int,
) -> Plan:
    preset = _GOAL_PRESETS.get(strategy)
    if not preset:
        available = ", ".join(sorted(_GOAL_PRESETS))
        raise ValueError(
            f"unknown orchestration strategy {strategy!r}; "
            f"available strategies: {available}"
        )
    node_payload = dict(payload or {})
    nodes: list[PlannedNode] = []
    prior: list[str] = []
    for idx, key in enumerate(preset[:max_nodes]):
        seq = idx
        nodes.append(PlannedNode(
            node_key=key,
            sequence=seq,
            depends_on=list(prior),
            payload=node_payload,
        ))
        prior = [key]
    _ = goal, ORCHESTRATION_PLANNER_VERSION  # documented
    return Plan(strategy=strategy, nodes=nodes)


__all__ = ["PlannedNode", "Plan", "plan_orchestration"]


def available_orchestration_strategies() -> list[tuple[str, str]]:
    descriptions = {
        "research_pipeline": "Evidence-first end-to-end research preparation pipeline.",
        "complete_pre_submission": "Prepare a manuscript for submission with quality and compliance gates.",
        "prepare_for_submission": "Run citation, academic QA, and publication compliance checks.",
        "resolve_qa_blockers": "Re-run QA around humanization and remediation.",
        "improve_citation_completeness": "Improve evidence coverage and citation completeness.",
        "reviewer_revision_plan": "Rebuild the academic QA view for reviewer revisions.",
        "roundtable_review": (
            "Three role-specific, evidence-grounded reviews with explicit disagreement capture."
        ),
    }
    return [(key, descriptions.get(key, key)) for key in sorted(_GOAL_PRESETS)]
