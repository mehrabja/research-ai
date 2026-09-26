"""M35 — domain primitives + state machine."""
from __future__ import annotations

import pytest

from app.domain.orchestration import (
    APPROVAL_GATED_ACTIONS,
    DEFAULT_BUDGET,
    FAILURE_CLASSES,
    M35_VERSION,
    NODE_STATUSES,
    RUN_STATUSES,
    NodeStatus,
    RunStatus,
    is_terminal_node,
    is_terminal_run,
    requires_approval,
    validate_node_transition,
    validate_run_transition,
)


def test_version() -> None:
    assert M35_VERSION == "m35.1"


def test_budget_has_required_keys() -> None:
    for k in (
        "max_nodes", "max_retries_per_node", "max_provider_calls",
        "max_wall_clock_seconds", "max_total_tokens",
        "max_evidence_volume", "max_generated_chars",
    ):
        assert k in DEFAULT_BUDGET


def test_run_statuses() -> None:
    assert set(RUN_STATUSES) == {
        "queued", "planning", "awaiting_approval", "executing",
        "paused", "blocked", "completed", "failed", "cancelled",
    }


def test_node_statuses() -> None:
    assert "pending" in NODE_STATUSES
    assert "running" in NODE_STATUSES
    assert "completed" in NODE_STATUSES


def test_terminal_helpers() -> None:
    assert is_terminal_run(RunStatus.COMPLETED.value)
    assert is_terminal_run(RunStatus.FAILED.value)
    assert is_terminal_run(RunStatus.CANCELLED.value)
    assert not is_terminal_run(RunStatus.EXECUTING.value)
    assert is_terminal_node(NodeStatus.COMPLETED.value)
    assert not is_terminal_node(NodeStatus.RUNNING.value)


def test_valid_run_transitions() -> None:
    validate_run_transition(
        RunStatus.QUEUED.value, RunStatus.PLANNING.value,
    )
    validate_run_transition(
        RunStatus.PLANNING.value, RunStatus.EXECUTING.value,
    )
    validate_run_transition(
        RunStatus.EXECUTING.value, RunStatus.COMPLETED.value,
    )
    validate_run_transition(
        RunStatus.EXECUTING.value, RunStatus.PAUSED.value,
    )
    validate_run_transition(
        RunStatus.PAUSED.value, RunStatus.EXECUTING.value,
    )


def test_invalid_run_transition() -> None:
    with pytest.raises(ValueError):
        validate_run_transition(
            RunStatus.COMPLETED.value, RunStatus.EXECUTING.value,
        )
    with pytest.raises(ValueError):
        validate_run_transition(
            RunStatus.QUEUED.value, RunStatus.COMPLETED.value,
        )


def test_valid_node_transitions() -> None:
    validate_node_transition(
        NodeStatus.PENDING.value, NodeStatus.RUNNING.value,
    )
    validate_node_transition(
        NodeStatus.RUNNING.value, NodeStatus.COMPLETED.value,
    )
    validate_node_transition(
        NodeStatus.RUNNING.value, NodeStatus.FAILED.value,
    )
    validate_node_transition(
        NodeStatus.FAILED.value, NodeStatus.PENDING.value,
    )


def test_invalid_node_transition() -> None:
    with pytest.raises(ValueError):
        validate_node_transition(
            NodeStatus.COMPLETED.value, NodeStatus.RUNNING.value,
        )


def test_approval_gates() -> None:
    assert requires_approval("submit_manuscript")
    assert requires_approval("bulk_rewrite")
    assert not requires_approval("build_plan")
    assert "submit_manuscript" in APPROVAL_GATED_ACTIONS


def test_failure_classes() -> None:
    for c in (
        "validation", "not_found", "conflict", "ownership",
        "unsupported", "provider_retryable", "provider_permanent",
        "timeout", "budget_exceeded", "stale_worker", "internal",
    ):
        assert c in FAILURE_CLASSES
