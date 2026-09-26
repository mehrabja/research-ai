"""M25 — Graph integrity validation."""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass
class GraphValidationResult:
    score: float
    errors: list[str]
    warnings: list[str]

    def valid(self) -> bool:
        return not self.errors


def validate_graph_structure(
    *,
    nodes: list[dict],
    edges: list[dict],
    project_id: str,
) -> GraphValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not nodes:
        errors.append("no nodes")
    if not edges:
        warnings.append("no edges")

    node_ids = {n["node_key"] for n in nodes}
    if len(node_ids) != len(nodes):
        errors.append("duplicate node_key")

    for n in nodes:
        if str(n.get("project_id")) != project_id:
            errors.append(f"cross-project node: {n['node_key']}")

    edge_ids: set[str] = set()
    for e in edges:
        if e["source_key"] not in node_ids:
            errors.append(f"edge source missing: {e['source_key']}")
        if e["target_key"] not in node_ids:
            errors.append(f"edge target missing: {e['target_key']}")
        if e["source_key"] == e["target_key"]:
            errors.append(f"self-loop edge: {e['edge_key']}")
        if e["edge_key"] in edge_ids:
            errors.append(f"duplicate edge_key: {e['edge_key']}")
        edge_ids.add(e["edge_key"])
        if str(e.get("project_id")) != project_id:
            errors.append(f"cross-project edge: {e['edge_key']}")

    total = max(1, len(nodes) + len(edges))
    passed = total - len(errors)
    score = max(0.0, passed / total)
    return GraphValidationResult(score=score, errors=errors, warnings=warnings)


def validate_persisted_edges(
    *,
    node_owner: dict[str, tuple[uuid.UUID, uuid.UUID]],
    edges: list[dict],
    project_id: uuid.UUID,
    graph_version_id: uuid.UUID,
) -> GraphValidationResult:
    errors: list[str] = []
    for e in edges:
        src = node_owner.get(e["source_key"])
        tgt = node_owner.get(e["target_key"])
        if src is None:
            errors.append(f"missing source node: {e['source_key']}")
            continue
        if tgt is None:
            errors.append(f"missing target node: {e['target_key']}")
            continue
        if src[0] != project_id or tgt[0] != project_id:
            errors.append(f"cross-project edge: {e['edge_key']}")
        if src[1] != graph_version_id or tgt[1] != graph_version_id:
            errors.append(f"cross-version edge: {e['edge_key']}")

    total = max(1, len(edges))
    score = max(0.0, (total - len(errors)) / total)
    return GraphValidationResult(score=score, errors=errors, warnings=[])
