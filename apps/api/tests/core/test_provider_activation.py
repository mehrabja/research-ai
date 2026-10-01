"""F20 provider activation gate tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "provider_activation.py"


spec = importlib.util.spec_from_file_location("provider_activation", SCRIPT)
assert spec is not None and spec.loader is not None
provider_activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider_activation)


def test_originality_requires_detection_key(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_PROVIDER", "originality")
    monkeypatch.delenv("AI_DETECTION_API_KEY", raising=False)

    checks = provider_activation.config_checks(strict=False)
    detection = next(c for c in checks if c.name == "AI detection provider")

    assert detection.ok is False
    assert "active originality" in detection.detail


def test_originality_passes_with_detection_key(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_PROVIDER", "originality")
    monkeypatch.setenv("AI_DETECTION_API_KEY", "realistic-test-secret")

    checks = provider_activation.config_checks(strict=False)
    detection = next(c for c in checks if c.name == "AI detection provider")

    assert detection.ok is True
    assert detection.detail == "active originality"
