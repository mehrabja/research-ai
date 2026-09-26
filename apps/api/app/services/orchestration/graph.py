"""M35 — Node/run state machine helpers."""
from __future__ import annotations

from app.domain.orchestration import (
    validate_node_transition,
    validate_run_transition,
)


def transition_run(from_status: str, to_status: str) -> None:
    validate_run_transition(from_status, to_status)


def transition_node(from_status: str, to_status: str) -> None:
    validate_node_transition(from_status, to_status)


def successors_of(
    *,
    all_nodes: list[tuple[str, list[str]]],
    completed: set[str],
) -> list[str]:
    """Deterministic traversal order.

    A node is eligible if all its dependencies are completed. The
    ordering is the caller-provided sequence (list order) which is
    stable by construction.
    """
    out: list[str] = []
    for node_key, deps in all_nodes:
        if node_key in completed:
            continue
        if all(d in completed for d in deps):
            out.append(node_key)
    return out


__all__ = ["transition_run", "transition_node", "successors_of"]
