"""M36 — retention policy contract tests."""
from __future__ import annotations

from app.services.retention import (
    NoopRetentionPolicy,
    RetentionDecision,
    get_retention_policy,
    set_retention_policy,
)


def test_noop_keeps_everything() -> None:
    p = NoopRetentionPolicy()
    d = p.evaluate(category="job", age_seconds=10_000_000)
    assert d.keep is True
    assert d.reason == "noop"


def test_default_policy_is_noop() -> None:
    assert isinstance(get_retention_policy(), NoopRetentionPolicy)


def test_replacement_and_reset() -> None:
    class _DeleteAll:
        def evaluate(self, *, category: str, age_seconds: float):
            return RetentionDecision(keep=False, reason="test")

    set_retention_policy(_DeleteAll())
    try:
        assert (
            get_retention_policy()
            .evaluate(category="x", age_seconds=0.0)
            .keep
            is False
        )
    finally:
        set_retention_policy(None)
    assert isinstance(get_retention_policy(), NoopRetentionPolicy)


def test_decision_requires_bool() -> None:
    import pytest

    with pytest.raises(TypeError):
        RetentionDecision(keep="yes")  # type: ignore[arg-type]
