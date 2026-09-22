"""M24 — Plan dependency DAG validation."""
from __future__ import annotations

from app.core.exceptions import ResearchPlanDependencyCycle


def detect_cycle(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[str] | None:
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, [])
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(adj, white)
    stack: list[str] = []

    def dfs(u: str) -> bool:
        color[u] = gray
        stack.append(u)
        for v in adj[u]:
            if color[v] == gray:
                return True
            if color[v] == white and dfs(v):
                return True
        stack.pop()
        color[u] = black
        return False

    for n in adj:
        if color[n] == white and dfs(n):
            return list(stack)
    return None


def validate_dependency_graph(
    nodes: list[str], edges: list[tuple[str, str]]
) -> None:
    seen: set[tuple[str, str]] = set()
    for u, v in edges:
        if u == v:
            raise ResearchPlanDependencyCycle(
                "self-dependency not allowed"
            )
        if (u, v) in seen:
            raise ResearchPlanDependencyCycle(
                "duplicate dependency edge"
            )
        seen.add((u, v))
    cycle = detect_cycle(nodes, edges)
    if cycle is not None:
        raise ResearchPlanDependencyCycle(
            "dependency cycle detected: " + " -> ".join(cycle)
        )


def topological_order(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[str]:
    validate_dependency_graph(nodes, edges)
    indeg: dict[str, int] = dict.fromkeys(nodes, 0)
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        adj[u].append(v)
        indeg[v] += 1
    queue = sorted([n for n in nodes if indeg[n] == 0])
    out: list[str] = []
    while queue:
        u = queue.pop(0)
        out.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
                queue.sort()
    return out


def section_dependency_template(
    section_keys: list[str],
) -> list[tuple[str, str]]:
    canonical = [
        "introduction", "background", "related_work", "methods",
        "results", "discussion", "limitations", "conclusion",
        "future_work", "appendix",
    ]
    present = [k for k in canonical if k in section_keys]
    extra = [k for k in section_keys if k not in canonical]
    ordered = present + extra
    edges: list[tuple[str, str]] = []
    for a, b in zip(ordered, ordered[1:], strict=False):
        edges.append((a, b))
    return edges
