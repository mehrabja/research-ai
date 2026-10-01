"""F17 production smoke helper regression coverage."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "production_smoke.py"

spec = importlib.util.spec_from_file_location("production_smoke", SCRIPT)
assert spec is not None and spec.loader is not None
production_smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = production_smoke
spec.loader.exec_module(production_smoke)


def test_required_rejects_missing_value(monkeypatch) -> None:
    monkeypatch.delenv("SMOKE_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="SMOKE_BASE_URL is required"):
        production_smoke.required("SMOKE_BASE_URL")


def test_required_rejects_placeholder_value(monkeypatch) -> None:
    monkeypatch.setenv("SMOKE_BASE_URL", "https://example.invalid")

    with pytest.raises(RuntimeError, match="placeholder"):
        production_smoke.required("SMOKE_BASE_URL")


def test_auth_headers_prefer_access_token(monkeypatch) -> None:
    monkeypatch.setenv("SMOKE_ACCESS_TOKEN", "access-token")
    monkeypatch.setenv("SMOKE_API_KEY", "api-key")

    assert production_smoke.auth_headers() == {
        "Accept": "application/json",
        "Authorization": "Bearer access-token",
    }


def test_auth_headers_support_api_key(monkeypatch) -> None:
    monkeypatch.delenv("SMOKE_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("SMOKE_API_KEY", "api-key")

    assert production_smoke.auth_headers() == {
        "Accept": "application/json",
        "X-API-Key": "api-key",
    }


def test_check_expected_providers_accepts_registered_provider(monkeypatch) -> None:
    matrix = {
        "capabilities": [
            {
                "capability": "generation",
                "configured_preferred": "openrouter",
                "available_providers": ["openai", "openrouter"],
            }
        ]
    }

    monkeypatch.setenv("SMOKE_EXPECT_PROVIDER", "generation=openrouter")
    production_smoke.check_expected_providers(matrix)


def test_check_expected_providers_rejects_unknown_provider(monkeypatch) -> None:
    matrix = {
        "capabilities": [
            {
                "capability": "generation",
                "configured_preferred": "openai",
                "available_providers": ["openai"],
            }
        ]
    }

    monkeypatch.setenv("SMOKE_EXPECT_PROVIDER", "generation=openrouter")
    with pytest.raises(RuntimeError, match="not configured/registered"):
        production_smoke.check_expected_providers(matrix)


def test_verify_originality_uses_balance_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("AI_DETECTION_API_KEY", "test-key")
    monkeypatch.setenv(
        "DETECTION_ORIGINALITY_BASE_URL",
        "https://api.originality.ai/api/v3",
    )
    seen: dict[str, object] = {}

    def fake_json_request(url: str, headers=None):
        seen["url"] = url
        seen["headers"] = headers
        return 200, {}, {"credits": 10, "subscriptionCredits": 20}

    monkeypatch.setattr(production_smoke, "json_request", fake_json_request)
    production_smoke.verify_originality()

    assert seen["url"] == (
        "https://api.originality.ai/api/v3/account/balance"
    )
    assert seen["headers"] == {
        "Accept": "application/json",
        "X-OAI-API-KEY": "test-key",
    }


def test_verify_originality_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("AI_DETECTION_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="AI_DETECTION_API_KEY"):
        production_smoke.verify_originality()
