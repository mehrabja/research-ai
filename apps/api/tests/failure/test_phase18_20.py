"""Phase 18-20 contract tests."""
from __future__ import annotations

from app.integrations.generation.base import (
    GenerationInvalidRequestError,
    GenerationProviderUnavailableError,
)
from app.providers.fallback import FallbackProvider


class _Transient:
    provider_name = "primary"
    model_name = "v1"

    def generate(self, **kwargs: object) -> dict[str, str]:
        raise GenerationProviderUnavailableError("temporary")


class _Permanent:
    provider_name = "primary"
    model_name = "v1"

    def generate(self, **kwargs: object) -> dict[str, str]:
        raise GenerationInvalidRequestError("bad request")


class _Healthy:
    provider_name = "secondary"
    model_name = "v1"

    def generate(self, **kwargs: object) -> dict[str, str]:
        return {"provider": self.provider_name}


def test_transient_provider_failure_recovers_with_fallback() -> None:
    provider = FallbackProvider((_Transient(), _Healthy()))
    result = provider.generate(
        system_prompt="system",
        user_prompt="user",
        temperature=0.2,
        max_output_tokens=32,
    )
    assert result == {"provider": "secondary"}


def test_permanent_provider_failure_does_not_skip_to_fallback() -> None:
    provider = FallbackProvider((_Permanent(), _Healthy()))
    try:
        provider.generate(
            system_prompt="system",
            user_prompt="user",
            temperature=0.2,
            max_output_tokens=32,
        )
    except GenerationInvalidRequestError as exc:
        assert str(exc) == "bad request"
    else:
        raise AssertionError("permanent provider error unexpectedly fell back")


def test_placeholder_credentials_are_not_configured(monkeypatch) -> None:
    from pathlib import Path
    import sys

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    monkeypatch.setenv("OPENROUTER_API_KEY", "YOUR_API_KEY")
    from scripts.provider_activation import configured

    assert configured("OPENROUTER_API_KEY") is False
