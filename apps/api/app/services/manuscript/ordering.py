"""M27 — Deterministic research ordering."""
from __future__ import annotations

from app.db.models.manuscript import (
    ManuscriptSection,
    ManuscriptSectionDependency,
)


def topological_research_order(
    *,
    section_keys: list[str],
    edges: list[tuple[str, str]],
) -> list[str]:
    indeg = dict.fromkeys(section_keys, 0)
    adj: dict[str, list[str]] = {n: [] for n in section_keys}
    for u, v in edges:
        if u not in adj or v not in adj:
            continue
        adj[u].append(v)
        indeg[v] += 1
    queue = sorted(n for n in section_keys if indeg[n] == 0)
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


def research_order_for_sections(
    *,
    sections: list[ManuscriptSection],
    dependencies: list[ManuscriptSectionDependency],
) -> list[str]:
    by_id = {s.id: s.section_key for s in sections}
    edges = [
        (by_id[d.upstream_section_id], by_id[d.downstream_section_id])
        for d in dependencies
        if d.upstream_section_id in by_id and d.downstream_section_id in by_id
    ]
    return topological_research_order(
        section_keys=[s.section_key for s in sections],
        edges=edges,
    )


__all__ = ["topological_research_order", "research_order_for_sections"]
