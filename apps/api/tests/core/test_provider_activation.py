"""F20 provider activation gate tests."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "provider_activation.py"


spec = importlib.util.spec_from_file_location("provider_activation", SCRIPT)
assert spec is not None and spec.loader is not None
provider_activation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = provider_activation
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


def test_strict_mode_rejects_heuristic_detection(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_PROVIDER", "heuristic")
    monkeypatch.delenv("AI_DETECTION_API_KEY", raising=False)

    checks = provider_activation.config_checks(strict=True)
    detection = next(c for c in checks if c.name == "AI detection provider")

    assert detection.ok is False
    assert detection.detail == "non-production baseline"


def test_http_detection_requires_base_url(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_PROVIDER", "http")
    monkeypatch.setenv("AI_DETECTION_API_KEY", "realistic-test-secret")
    monkeypatch.delenv("DETECTION_API_BASE_URL", raising=False)

    checks = provider_activation.config_checks(strict=False)
    detection = next(c for c in checks if c.name == "AI detection provider")

    assert detection.ok is False


def test_unknown_detection_provider_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_PROVIDER", "unknown-provider")
    monkeypatch.delenv("AI_DETECTION_API_KEY", raising=False)

    checks = provider_activation.config_checks(strict=False)
    detection = next(c for c in checks if c.name == "AI detection provider")

    assert detection.ok is False
    assert detection.detail == "unsupported provider"


def test_originality_external_check_reads_account_balance(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_PROVIDER", "originality")
    monkeypatch.setenv("AI_DETECTION_API_KEY", "test-key")
    monkeypatch.setattr(
        provider_activation,
        "http_json",
        lambda url, headers=None: (
            200,
            {"credits": 10, "subscriptionCredits": 20},
        ),
    )

    check = provider_activation.external_check("Originality.ai")

    assert check.ok is True
    assert check.detail == "read-only verification"


def test_originality_external_check_skips_when_inactive(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_PROVIDER", "heuristic")
    monkeypatch.delenv("AI_DETECTION_API_KEY", raising=False)

    check = provider_activation.external_check("Originality.ai")

    assert check.ok is True
    assert check.detail == "skipped; provider not active"

class _FakeStripeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"object":"balance","available":[],"pending":[]}'


def test_stripe_external_check_is_read_only(monkeypatch) -> None:
    monkeypatch.setenv("BILLING_PROVIDER", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "test-key")
    monkeypatch.setattr(
        provider_activation.urllib.request,
        "urlopen",
        lambda request, timeout=15: _FakeStripeResponse(),
    )

    check = provider_activation.external_check("Stripe")

    assert check.ok is True
    assert check.detail == "read-only verification"
