from __future__ import annotations

import pytest

from app.providers.fallback import FallbackProvider
from app.providers.registry import (
    ProviderCapability,
    ProviderContext,
    ProviderRegistry,
    ProviderResolutionError,
)


class StubGeneration:
    provider_name = "stub"
    model_name = "stub-v1"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def generate(self, **kwargs: object) -> dict[str, str]:
        if self.fail:
            from app.integrations.generation.base import (
                GenerationProviderUnavailableError,
            )

            raise GenerationProviderUnavailableError("temporary")
        return {"provider": self.provider_name}


def test_registry_resolves_preferred_then_fallback() -> None:
    registry = ProviderRegistry()
    registry.register(
        capability=ProviderCapability.GENERATION,
        name="primary",
        factory=lambda ctx: StubGeneration(fail=True),
    )
    registry.register(
        capability=ProviderCapability.GENERATION,
        name="secondary",
        factory=lambda ctx: StubGeneration(),
    )

    chain = registry.resolve_chain(
        capability=ProviderCapability.GENERATION,
        preferred="primary",
        fallbacks=("secondary", "unknown", "secondary"),
        context=ProviderContext(),
    )

    assert len(chain) == 2
    assert [p.provider_name for p in chain] == ["stub", "stub"]


def test_registry_raises_when_nothing_is_registered() -> None:
    registry = ProviderRegistry()
    with pytest.raises(ProviderResolutionError) as exc:
        registry.resolve(
            capability=ProviderCapability.TRANSLATION,
            preferred="missing",
        )
    assert exc.value.capability == ProviderCapability.TRANSLATION
    assert exc.value.attempted == ("missing",)


def test_fallback_provider_advances_only_on_transient_failure() -> None:
    primary = StubGeneration(fail=True)
    secondary = StubGeneration()
    provider = FallbackProvider((primary, secondary))

    result = provider.generate()

    assert result == {"provider": "stub"}
    assert provider.model_name == "stub-v1"


def test_registry_registers_originality_detection_provider() -> None:
    registry = ProviderRegistry()

    from app.integrations.detection.originality import OriginalityDetectionProvider

    registry.register(
        capability=ProviderCapability.DETECTION,
        name="originality",
        factory=lambda ctx: OriginalityDetectionProvider(),
    )

    provider = registry.resolve(
        capability=ProviderCapability.DETECTION,
        preferred="originality",
    )
    assert provider.provider_name == "originality"
    assert isinstance(provider, OriginalityDetectionProvider)
