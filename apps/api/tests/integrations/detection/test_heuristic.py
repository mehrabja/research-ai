"""Heuristic provider tests (no DB)."""
from __future__ import annotations

from app.integrations.detection.heuristic import (
    HeuristicDetectionProvider,
)


def test_empty_text_returns_unknown() -> None:
    r = HeuristicDetectionProvider().detect(text="")
    assert r.probability is None
    assert r.raw_label == "unknown"
    assert r.input_chars == 0


def test_typical_text_returns_probability() -> None:
    text = (
        "This is a normal sentence. "
        "Another sentence follows here. "
        "A third one concludes the paragraph."
    )
    r = HeuristicDetectionProvider().detect(text=text)
    assert r.probability is not None
    assert 0.0 <= r.probability <= 1.0
    assert r.input_chars == len(text)


def test_deterministic() -> None:
    text = "Alpha. Beta. Gamma."
    a = HeuristicDetectionProvider().detect(text=text)
    b = HeuristicDetectionProvider().detect(text=text)
    assert a.probability == b.probability
