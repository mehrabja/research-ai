"""M35 — Approval-gate policy."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.domain.orchestration import APPROVAL_GATED_ACTIONS


@dataclass
class PolicyDecision:
    approval_required: bool
    action_key: str | None = None


def evaluate_node_policy(
    *,
    node_key: str,
    node_type: str,
    deterministic: bool,
) -> PolicyDecision:
    """Decide whether this node requires human approval before running.

    Rules (deterministic):
      - human_approval node_type always requires approval
      - explicit action_key in APPROVAL_GATED_ACTIONS requires approval
      - otherwise, config ``orchestration_require_approval`` controls
        model_assisted nodes (LLM output must be approved by default)
    """
    if node_type == "human_approval":
        return PolicyDecision(
            approval_required=True, action_key=node_key,
        )
    if node_key in APPROVAL_GATED_ACTIONS:
        return PolicyDecision(
            approval_required=True, action_key=node_key,
        )
    settings = get_settings()
    if (
        not deterministic
        and settings.orchestration_require_approval
    ):
        return PolicyDecision(
            approval_required=True, action_key=node_key,
        )
    return PolicyDecision(approval_required=False)


__all__ = ["PolicyDecision", "evaluate_node_policy"]
