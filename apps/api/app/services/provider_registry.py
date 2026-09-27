"""M39 provider registry and configuration-driven provider resolution.

The registry is deliberately small and dependency-light.  It centralizes
provider selection without pretending that an unconfigured provider exists.
Concrete providers are imported lazily inside factories to avoid import
cycles and to keep provider SDK/network initialization out of module import.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal, cast

from app.core.config import get_settings
from app.domain.embeddings import EmbeddingProfile
from app.domain.generation import GenerationProfile

ProviderCapability = Literal["generation", "embedding", "translation"]

if TYPE_CHECKING:
    from app.services.translation_profile import TranslationProfile





class ProviderResolutionError(RuntimeError):
    """Base error for provider-policy resolution."""





class ProviderNotConfiguredError(ProviderResolutionError):
    """No configured provider is registered for the requested capability."""

@dataclass(frozen=True)
class ProviderDefinition:
    name: str
    capability: ProviderCapability
    factory: Callable[[Any], Any]
    enabled: bool = True


class ProviderRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[ProviderCapability, str], ProviderDefinition] = {}

    def register(self, definition: ProviderDefinition) -> None:
        key = (definition.capability, definition.name)
        if key in self._definitions:
            raise ValueError(
                f"provider already registered: {definition.capability}/{definition.name}"
            )
        self._definitions[key] = definition

    def definitions(self, capability: ProviderCapability) -> tuple[ProviderDefinition, ...]:
        return tuple(
            d for (cap, _), d in self._definitions.items()
            if cap == capability and d.enabled
        )

    def configured_chain(self, capability: ProviderCapability) -> tuple[str, ...]:
        settings = get_settings()
        raw = {
            "generation": settings.provider_generation_chain,
            "embedding": settings.provider_embedding_chain,
            "translation": settings.provider_translation_chain,
        }[capability]
        names = tuple(name.strip().lower() for name in raw.split(",") if name.strip())
        if not names:
            raise ProviderNotConfiguredError(
                f"no providers configured for capability {capability!r}"
            )
        return names

    def candidates(
        self,
        capability: ProviderCapability,
        *,
        requested: str | None = None,
    ) -> tuple[ProviderDefinition, ...]:
        ordered_names = (
            (requested.strip().lower(),)
            if requested and requested.strip()
            else self.configured_chain(capability)
        )
        result: list[ProviderDefinition] = []
        for name in ordered_names:
            definition = self._definitions.get((capability, name))
            if definition is not None and definition.enabled:
                result.append(definition)
        if not result:
            available = ", ".join(
                d.name for d in self.definitions(capability)
            ) or "none"
            raise ProviderNotConfiguredError(
                f"no registered provider for {capability!r}; requested/configured="
                f"{ordered_names!r}; registered={available}"
            )
        return tuple(result)

    def resolve(
        self,
        capability: ProviderCapability,
        *,
        requested: str | None = None,
        config: Any = None,
    ) -> Any:
        definitions = self.candidates(capability, requested=requested)
        return definitions[0].factory(config)


def _build_generation(config: GenerationProfile | None) -> Any:
    from app.integrations.generation.openai import OpenAIGenerationProvider
    profile = config or __import__(
        "app.services.generation_profile",
        fromlist=["get_current_generation_profile"],
    ).get_current_generation_profile()
    s = get_settings()
    if profile.provider != "openai":
        raise ProviderNotConfiguredError(
            f"generation provider {profile.provider!r} is not registered"
        )
    return OpenAIGenerationProvider(
        model=profile.model,
        base_url=s.generation_openai_base_url or None,
        api_key=s.generation_openai_api_key or None,
        timeout_seconds=s.generation_timeout_seconds,
        max_retries=s.generation_max_retries,
        retry_base_seconds=s.generation_retry_base_seconds,
        retry_max_seconds=s.generation_retry_max_seconds,
        retry_jitter_fraction=s.generation_retry_jitter_fraction,
    )


def _build_embedding(config: EmbeddingProfile | None) -> Any:
    from app.integrations.embeddings.openai import OpenAIEmbeddingProvider
    profile = config or __import__(
        "app.services.embedding_profile",
        fromlist=["get_current_embedding_profile"],
    ).get_current_embedding_profile()
    if profile.provider != "openai":
        raise ProviderNotConfiguredError(
            f"embedding provider {profile.provider!r} is not registered"
        )
    return OpenAIEmbeddingProvider(profile=profile)


def _build_translation(config: TranslationProfile | None) -> Any:
    from app.integrations.generation.openai import OpenAIGenerationProvider
    from app.integrations.translation.openai import OpenAITranslationProvider
    profile = config or __import__(
        "app.services.translation_profile",
        fromlist=["get_current_translation_profile"],
    ).get_current_translation_profile()
    s = get_settings()
    if profile.provider != "openai":
        raise ProviderNotConfiguredError(
            f"translation provider {profile.provider!r} is not registered"
        )
    generation = OpenAIGenerationProvider(
        model=profile.model,
        base_url=s.generation_openai_base_url or None,
        api_key=s.generation_openai_api_key or None,
        timeout_seconds=profile.timeout_seconds,
        max_retries=profile.max_retries,
        retry_base_seconds=profile.retry_base_seconds,
        retry_max_seconds=profile.retry_max_seconds,
        retry_jitter_fraction=profile.retry_jitter_fraction,
    )
    return OpenAITranslationProvider(
        generation_provider=generation,
        model_name=profile.model,
    )


def build_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(
        ProviderDefinition(
            name="openai",
            capability="generation",
            factory=_build_generation,
        )
    )
    registry.register(
        ProviderDefinition(
            name="openai",
            capability="embedding",
            factory=_build_embedding,
        )
    )
    registry.register(
        ProviderDefinition(
            name="openai",
            capability="translation",
            factory=_build_translation,
        )
    )
    return registry


def get_provider_registry() -> ProviderRegistry:
    return build_provider_registry()


def build_generation_provider(profile: GenerationProfile | None = None) -> Any:
    registry = get_provider_registry()
    requested = profile.provider if profile is not None else None
    return cast(Any, registry.resolve("generation", requested=requested, config=profile))


def build_embedding_provider(profile: EmbeddingProfile | None = None) -> Any:
    registry = get_provider_registry()
    requested = profile.provider if profile is not None else None
    return cast(Any, registry.resolve("embedding", requested=requested, config=profile))


def build_translation_provider(profile: TranslationProfile) -> Any:
    registry = get_provider_registry()
    return cast(
        Any,
        registry.resolve("translation", requested=profile.provider, config=profile),
    )
