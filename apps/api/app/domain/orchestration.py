"""M35 — Agentic research orchestration domain primitives."""
from __future__ import annotations

from enum import StrEnum

M35_VERSION = "m35.1"
ORCHESTRATION_PLANNER_VERSION = "m39-planner-v2"
ORCHESTRATION_TOOL_REGISTRY_VERSION = "m39-tools-v2"


class RunStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class NodeType(StrEnum):
    DETERMINISTIC = "deterministic"
    MODEL_ASSISTED = "model_assisted"
    HUMAN_APPROVAL = "human_approval"


class FailureClass(StrEnum):
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    OWNERSHIP = "ownership"
    UNSUPPORTED = "unsupported"
    PROVIDER_RETRYABLE = "provider_retryable"
    PROVIDER_PERMANENT = "provider_permanent"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"
    STALE_WORKER = "stale_worker"
    INTERNAL = "internal"


RUN_STATUSES = tuple(s.value for s in RunStatus)
NODE_STATUSES = tuple(s.value for s in NodeStatus)
NODE_TYPES = tuple(t.value for t in NodeType)
FAILURE_CLASSES = tuple(f.value for f in FailureClass)

# Deterministic run state machine.
_RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    RunStatus.QUEUED.value: frozenset({
        RunStatus.PLANNING.value,
        RunStatus.CANCELLED.value,
        RunStatus.FAILED.value,
    }),
    RunStatus.PLANNING.value: frozenset({
        RunStatus.EXECUTING.value,
        RunStatus.AWAITING_APPROVAL.value,
        RunStatus.FAILED.value,
        RunStatus.CANCELLED.value,
    }),
    RunStatus.AWAITING_APPROVAL.value: frozenset({
        RunStatus.EXECUTING.value,
        RunStatus.CANCELLED.value,
        RunStatus.FAILED.value,
    }),
    RunStatus.EXECUTING.value: frozenset({
        RunStatus.AWAITING_APPROVAL.value,
        RunStatus.PAUSED.value,
        RunStatus.BLOCKED.value,
        RunStatus.COMPLETED.value,
        RunStatus.FAILED.value,
        RunStatus.CANCELLED.value,
    }),
    RunStatus.PAUSED.value: frozenset({
        RunStatus.EXECUTING.value,
        RunStatus.CANCELLED.value,
    }),
    RunStatus.BLOCKED.value: frozenset({
        RunStatus.EXECUTING.value,
        RunStatus.FAILED.value,
        RunStatus.CANCELLED.value,
    }),
    RunStatus.COMPLETED.value: frozenset(),
    RunStatus.FAILED.value: frozenset(),
    RunStatus.CANCELLED.value: frozenset(),
}

# Deterministic node state machine.
_NODE_TRANSITIONS: dict[str, frozenset[str]] = {
    NodeStatus.PENDING.value: frozenset({
        NodeStatus.RUNNING.value,
        NodeStatus.AWAITING_APPROVAL.value,
        NodeStatus.SKIPPED.value,
        NodeStatus.BLOCKED.value,
    }),
    NodeStatus.AWAITING_APPROVAL.value: frozenset({
        NodeStatus.RUNNING.value,
        NodeStatus.SKIPPED.value,
        NodeStatus.BLOCKED.value,
    }),
    NodeStatus.RUNNING.value: frozenset({
        NodeStatus.COMPLETED.value,
        NodeStatus.FAILED.value,
        NodeStatus.BLOCKED.value,
    }),
    NodeStatus.FAILED.value: frozenset({
        NodeStatus.PENDING.value,  # retry
    }),
    NodeStatus.BLOCKED.value: frozenset({
        NodeStatus.PENDING.value,
    }),
    NodeStatus.COMPLETED.value: frozenset(),
    NodeStatus.SKIPPED.value: frozenset(),
}

_TERMINAL_RUN_STATUSES = frozenset({
    RunStatus.COMPLETED.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
})

_TERMINAL_NODE_STATUSES = frozenset({
    NodeStatus.COMPLETED.value,
    NodeStatus.SKIPPED.value,
})


def validate_run_transition(from_status: str, to_status: str) -> None:
    if from_status not in RUN_STATUSES:
        raise ValueError(f"unknown from_status: {from_status!r}")
    if to_status not in RUN_STATUSES:
        raise ValueError(f"unknown to_status: {to_status!r}")
    if from_status == to_status:
        return
    allowed = _RUN_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise ValueError(
            f"invalid run transition: {from_status} -> {to_status}"
        )


def validate_node_transition(from_status: str, to_status: str) -> None:
    if from_status not in NODE_STATUSES:
        raise ValueError(f"unknown from_status: {from_status!r}")
    if to_status not in NODE_STATUSES:
        raise ValueError(f"unknown to_status: {to_status!r}")
    if from_status == to_status:
        return
    allowed = _NODE_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise ValueError(
            f"invalid node transition: {from_status} -> {to_status}"
        )


def is_terminal_run(status: str) -> bool:
    return status in _TERMINAL_RUN_STATUSES


def is_terminal_node(status: str) -> bool:
    return status in _TERMINAL_NODE_STATUSES


# Default budgets. All are upper bounds; exceeding any produces a
# terminal blocked/failed state.
DEFAULT_BUDGET: dict[str, int] = {
    "max_nodes": 50,
    "max_retries_per_node": 3,
    "max_provider_calls": 100,
    "max_wall_clock_seconds": 3600,
    "max_total_tokens": 500_000,
    "max_evidence_volume": 1000,
    "max_generated_chars": 2_000_000,
}

# Operations that require human approval before execution.
APPROVAL_GATED_ACTIONS: frozenset[str] = frozenset({
    "submit_manuscript",
    "replace_final_manuscript",
    "destructive_merge",
    "bulk_rewrite",
    "replace_target_profile",
    "change_strategy",
    "exceed_budget",
})


def requires_approval(action_key: str) -> bool:
    return action_key in APPROVAL_GATED_ACTIONS


__all__ = [
    "M35_VERSION",
    "ORCHESTRATION_PLANNER_VERSION",
    "ORCHESTRATION_TOOL_REGISTRY_VERSION",
    "RunStatus",
    "NodeStatus",
    "NodeType",
    "FailureClass",
    "RUN_STATUSES",
    "NODE_STATUSES",
    "NODE_TYPES",
    "FAILURE_CLASSES",
    "DEFAULT_BUDGET",
    "APPROVAL_GATED_ACTIONS",
    "validate_run_transition",
    "validate_node_transition",
    "is_terminal_run",
    "is_terminal_node",
    "requires_approval",
]
