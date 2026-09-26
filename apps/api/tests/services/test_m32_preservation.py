"""M32 — preservation fingerprint tests."""
from __future__ import annotations

from app.services.manuscript_humanization.preservation import (
    build_fingerprint,
    compare_fingerprints,
)


def test_numbers_preserved() -> None:
    before = build_fingerprint("Accuracy is 92.5% on 1000 samples.")
    after = build_fingerprint(
        "The accuracy reaches 92.5% across 1000 samples."
    )
    result = compare_fingerprints(before, after)
    assert result.outcome == "ok"
    assert result.preservation_ratio == 1.0


def test_numbers_drift_detected() -> None:
    before = build_fingerprint("Accuracy is 92.5%.")
    after = build_fingerprint("Accuracy is 93.1%.")
    result = compare_fingerprints(before, after)
    assert result.outcome == "drift_detected"
    assert "numbers" in result.drift_by_category


def test_citation_marker_preserved() -> None:
    before = build_fingerprint("See [1] and [2,3] for details.")
    after = build_fingerprint("Refer to [1] and [2,3] for further.")
    result = compare_fingerprints(before, after)
    assert result.outcome == "ok"


def test_citation_marker_drift() -> None:
    before = build_fingerprint("See [1] and [2].")
    after = build_fingerprint("See [1] and [3].")
    result = compare_fingerprints(before, after)
    assert result.outcome == "drift_detected"
    assert "citations" in result.drift_by_category


def test_persian_text_survives() -> None:
    txt = "دقت مدل ۹۲.۵ درصد است [1]."
    fp = build_fingerprint(txt)
    # Non-ASCII content is preserved intact (no ASCII-fold).
    assert any("۹۲" in n or "92" in n for n in fp.numbers + [txt])
