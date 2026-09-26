"""Provider-neutral retention hooks (M36).

M36 defines only the CONTRACT. No deletion happens by default. Future
milestones (M37+) may register concrete policies to enforce retention
per category.

Categories are short strings, e.g.::

    "report_event"
    "file_event"
    "usage_log"
    "job"
    "backup"

Policies must NEVER delete research data (reports, sources, manuscript
versions, evidence) unless an explicit business rule from a later
milestone says so.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionDecision:
    keep: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.keep, bool):
            raise TypeError("keep must be a bool")


@runtime_checkable
class RetentionPolicy(Protocol):
    """Decide whether a row in ``category`` older than ``age_seconds``
    should be kept or deleted."""

    def evaluate(
        self, *, category: str, age_seconds: float
    ) -> RetentionDecision: ...


class NoopRetentionPolicy:
    """Default policy. Never deletes anything."""

    def evaluate(
        self, *, category: str, age_seconds: float
    ) -> RetentionDecision:
        return RetentionDecision(keep=True, reason="noop")


_policy: RetentionPolicy = NoopRetentionPolicy()


def get_retention_policy() -> RetentionPolicy:
    return _policy


def set_retention_policy(policy: RetentionPolicy | None) -> None:
    """Register a policy. Passing ``None`` restores the no-op default."""
    global _policy
    _policy = policy if policy is not None else NoopRetentionPolicy()


__all__ = [
    "NoopRetentionPolicy",
    "RetentionDecision",
    "RetentionPolicy",
    "get_retention_policy",
    "set_retention_policy",
]
