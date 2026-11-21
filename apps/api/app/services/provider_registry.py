"""M39 provider registry and configuration-driven provider resolution.

The registry is deliberately small and dependency-light.  It centralizes
provider selection without pretending that an unconfigured provider exists.
Concrete providers are imported lazily inside factories to avoid import
cycles and to keep provider SDK/network initialization out of module import.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, cast

from app.core.config import get_settings
from app.domain.embeddings import EmbeddingProfile
from app.domain.generation import GenerationProfile

if TYPE_CHECKING:
    from app.services.translation_profile import TranslationProfile


ProviderCapability = Literal["generation", "embedding", "translation"]


class GenerationProviderFallback:
    def __init__(self, providers: tuple[Any, ...]) -> None:
        self._providers = providers
        self.provider_name = getattr(providers[0], "provider_name", "router")
        self.model_name = getattr(providers[0], "model_name", "")
        self.last_used_provider_name = self.provider_name
        self.attempted_providers: list[str] = []

    def generate(self, **kwargs: Any) -> Any:
        from app.integrations.generation.base import (
            GenerationProviderUnavailableError,
            GenerationRateLimitError,
            GenerationTimeoutError,
        )
        last: Exception | None = None
        for provider in self._providers:
            name = getattr(provider, "provider_name", self.provider_name)
            self.attempted_providers.append(name)
            try:
                result = provider.generate(**kwargs)
                self.last_used_provider_name = getattr(result, "provider", name)
                return result
            except (
                GenerationRateLimitError,
                GenerationTimeoutError,
                GenerationProviderUnavailableError,
            ) as exc:
                last = exc
                continue
        assert last is not None
        raise last

    def generate_stream(self, **kwargs: Any) -> Any:
        from app.integrations.generation.base import (
            GenerationProviderUnavailableError,
            GenerationRateLimitError,
            GenerationTimeoutError,
        )
        original_callback = kwargs.pop("on_delta")
        emitted = False
        last: Exception | None = None
        for provider in self._providers:
            name = getattr(provider, "provider_name", self.provider_name)
            self.attempted_providers.append(name)

            def forward_delta(delta: str) -> None:
                nonlocal emitted
                emitted = True
                original_callback(delta)

            try:
                method = getattr(provider, "generate_stream", None)
                if callable(method):
                    result = method(**kwargs, on_delta=forward_delta)
                else:
                    result = provider.generate(**kwargs)
                    if result.text:
                        forward_delta(result.text)
                self.last_used_provider_name = getattr(result, "provider", name)
                return result
            except (
                GenerationRateLimitError,
                GenerationTimeoutError,
                GenerationProviderUnavailableError,
            ) as exc:
                if emitted:
                    raise
                last = exc
                continue
        assert last is not None
        raise last


class TranslationProviderFallback:
    def __init__(self, providers: tuple[Any, ...]) -> None:
        self._providers = providers
        self.provider_name = getattr(providers[0], "provider_name", "router")
        self.model_name = getattr(providers[0], "model_name", "")
        self.last_used_provider_name = self.provider_name
        self.attempted_providers: list[str] = []

    def translate(self, **kwargs: Any) -> Any:
        from app.integrations.translation.base import (
            TranslationProviderUnavailableError,
            TranslationRateLimitError,
            TranslationTimeoutError,
        )
        last: Exception | None = None
        for provider in self._providers:
            name = getattr(provider, "provider_name", self.provider_name)
            self.attempted_providers.append(name)
            try:
                result = provider.translate(**kwargs)
                self.last_used_provider_name = getattr(result, "provider", name)
                return result
            except (
                TranslationRateLimitError,
                TranslationTimeoutError,
                TranslationProviderUnavailableError,
            ) as exc:
                last = exc
                continue
        assert last is not None
        raise last


class EmbeddingProviderFallback:
    def __init__(self, providers: tuple[Any, ...]) -> None:
        dimensions = {
            getattr(p, "dimensions", None) for p in providers
        }
        if len(dimensions) != 1:
            raise ProviderNotConfiguredError(
                "embedding fallback providers must share vector dimensions"
            )
        self._providers = providers
        first = providers[0]
        self.provider_name = getattr(first, "provider_name", "router")
        self.model_name = getattr(first, "model_name", "")
        self.dimensions = first.dimensions
        self.max_batch_size = min(
            getattr(p, "max_batch_size", 1) for p in providers
        )
        self.max_input_tokens_per_item = getattr(
            first, "max_input_tokens_per_item", None
        )
        self.max_input_tokens_per_request = getattr(
            first, "max_input_tokens_per_request", None
        )
        self.last_used_provider_name = self.provider_name
        self.attempted_providers: list[str] = []

    def estimate_input_tokens(self, text: str) -> int | None:
        return self._providers[0].estimate_input_tokens(text)

    def embed_documents(self, texts: Any) -> Any:
        from app.integrations.embeddings.base import (
            EmbeddingProviderUnavailableError,
            EmbeddingRateLimitError,
        )
        last: Exception | None = None
        for provider in self._providers:
            name = getattr(provider, "provider_name", self.provider_name)
            self.attempted_providers.append(name)
            try:
                result = provider.embed_documents(texts)
                self.last_used_provider_name = getattr(result, "provider", name)
                return result
            except (
                EmbeddingRateLimitError,
                EmbeddingProviderUnavailableError,
            ) as exc:
                last = exc
                continue
        assert last is not None
        raise last

    def embed_query(self, text: str) -> list[float]:
        from app.integrations.embeddings.base import (
            EmbeddingProviderUnavailableError,
            EmbeddingRateLimitError,
        )
        last: Exception | None = None
        for provider in self._providers:
            name = getattr(provider, "provider_name", self.provider_name)
            self.attempted_providers.append(name)
            try:
                vector = provider.embed_query(text)
                self.last_used_provider_name = name
                return vector
            except (
                EmbeddingRateLimitError,
                EmbeddingProviderUnavailableError,
            ) as exc:
                last = exc
                continue
        assert last is not None
        raise last


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
        self._definitions: dict[
            tuple[ProviderCapability, str], ProviderDefinition
        ] = {}

    def register(self, definition: ProviderDefinition) -> None:
        key = (definition.capability, definition.name)
        if key in self._definitions:
            raise ValueError(
                f"provider already registered: {definition.capability}/{definition.name}"
            )
        self._definitions[key] = definition

    def definitions(
        self, capability: ProviderCapability
    ) -> tuple[ProviderDefinition, ...]:
        return tuple(
            d for (cap, _), d in self._definitions.items()
            if cap == capability and d.enabled
        )

    def configured_chain(
        self, capability: ProviderCapability
    ) -> tuple[str, ...]:
        settings = get_settings()
        raw = {
            "generation": settings.provider_generation_chain,
            "embedding": settings.provider_embedding_chain,
            "translation": settings.provider_translation_chain,
        }[capability]
        names = tuple(
            name.strip().lower()
            for name in raw.split(",")
            if name.strip()
        )
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
        configured = self.configured_chain(capability)
        if requested and requested.strip():
            preferred = requested.strip().lower()
            if preferred not in configured:
                raise ProviderNotConfiguredError(
                    f"requested provider {preferred!r} is not enabled "
                    f"for {capability!r}; configured={configured!r}"
                )
            ordered_names = (
                preferred,
                *tuple(name for name in configured if name != preferred),
            )
        else:
            ordered_names = configured
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
                f"no registered provider for {capability!r}; "
                f"requested/configured={ordered_names!r}; "
                f"registered={available}"
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
        providers_list: list[Any] = []
        for definition in definitions:
            try:
                providers_list.append(definition.factory(config))
            except ProviderNotConfiguredError:
                continue
        if not providers_list:
            raise ProviderNotConfiguredError(
                f"no configured provider implementation for {capability!r}; "
                f"candidates={tuple(d.name for d in definitions)!r}"
            )
        providers = tuple(providers_list)
        if len(providers) == 1:
            return providers[0]
        router_types = {
            "generation": GenerationProviderFallback,
            "embedding": EmbeddingProviderFallback,
            "translation": TranslationProviderFallback,
        }
        return router_types[capability](providers)


def _normalize_openai_compatible_model(model: str) -> str:
    return model.split("/", 1)[1] if model.startswith("openai/") else model


def _normalize_openrouter_model(model: str) -> str:
    return model if "/" in model else "openai/" + model


def _build_generation(provider_name: str, config: GenerationProfile | None) -> Any:
    from app.integrations.generation.openai import OpenAIGenerationProvider

    profile = config or __import__(
        "app.services.generation_profile",
        fromlist=["get_current_generation_profile"],
    ).get_current_generation_profile()
    s = get_settings()
    if provider_name == "openrouter":
        return OpenAIGenerationProvider(
            model=_normalize_openrouter_model(profile.model),
            base_url=s.openrouter_base_url,
            api_key=s.openrouter_api_key,
            provider_name="openrouter",
            timeout_seconds=s.generation_timeout_seconds,
            max_retries=s.generation_max_retries,
            retry_base_seconds=s.generation_retry_base_seconds,
            retry_max_seconds=s.generation_retry_max_seconds,
            retry_jitter_fraction=s.generation_retry_jitter_fraction,
        )
    if provider_name == "openai":
        if not s.generation_openai_api_key.strip():
            raise ProviderNotConfiguredError("GENERATION_OPENAI_API_KEY is not configured")
        return OpenAIGenerationProvider(
            model=_normalize_openai_compatible_model(profile.model),
            base_url=s.generation_openai_base_url or None,
            api_key=s.generation_openai_api_key or None,
            provider_name="openai",
            timeout_seconds=s.generation_timeout_seconds,
            max_retries=s.generation_max_retries,
            retry_base_seconds=s.generation_retry_base_seconds,
            retry_max_seconds=s.generation_retry_max_seconds,
            retry_jitter_fraction=s.generation_retry_jitter_fraction,
        )
    raise ProviderNotConfiguredError(
        f"generation provider {profile.provider!r} is not registered"
    )


def _build_embedding(provider_name: str, config: EmbeddingProfile | None) -> Any:
    from app.integrations.embeddings.openai import OpenAIEmbeddingProvider

    profile = config or __import__(
        "app.services.embedding_profile",
        fromlist=["get_current_embedding_profile"],
    ).get_current_embedding_profile()
    s = get_settings()
    if provider_name == "openrouter":
        if not s.openrouter_api_key.strip():
            raise ProviderNotConfiguredError("OPENROUTER_API_KEY is not configured")
        return OpenAIEmbeddingProvider(
            profile=profile,
            api_key=s.openrouter_api_key,
            base_url=s.openrouter_base_url,
            provider_name="openrouter",
        )
    if provider_name == "openai":
        if not s.embedding_openai_api_key.strip():
            raise ProviderNotConfiguredError("EMBEDDING_OPENAI_API_KEY is not configured")
        return OpenAIEmbeddingProvider(
            profile=profile,
            api_key=s.embedding_openai_api_key or None,
            base_url=s.embedding_openai_base_url or None,
            provider_name="openai",
        )
    raise ProviderNotConfiguredError(
        f"embedding provider {profile.provider!r} is not registered"
    )


def _build_translation(provider_name: str, config: TranslationProfile | None) -> Any:
    from app.integrations.generation.openai import OpenAIGenerationProvider
    from app.integrations.translation.openai import OpenAITranslationProvider

    profile = config or __import__(
        "app.services.translation_profile",
        fromlist=["get_current_translation_profile"],
    ).get_current_translation_profile()
    s = get_settings()
    if provider_name == "openrouter":
        generation = OpenAIGenerationProvider(
            model=_normalize_openrouter_model(profile.model),
            base_url=s.openrouter_base_url,
            api_key=s.openrouter_api_key,
            provider_name="openrouter",
            timeout_seconds=profile.timeout_seconds,
            max_retries=profile.max_retries,
            retry_base_seconds=profile.retry_base_seconds,
            retry_max_seconds=profile.retry_max_seconds,
            retry_jitter_fraction=profile.retry_jitter_fraction,
        )
        return OpenAITranslationProvider(
            generation_provider=generation,
            model_name=profile.model,
            provider_name="openrouter",
        )
    if provider_name == "openai":
        if not s.generation_openai_api_key.strip():
            raise ProviderNotConfiguredError("GENERATION_OPENAI_API_KEY is not configured")
        generation = OpenAIGenerationProvider(
            model=_normalize_openai_compatible_model(profile.model),
            base_url=s.generation_openai_base_url or None,
            api_key=s.generation_openai_api_key or None,
            provider_name="openai",
            timeout_seconds=profile.timeout_seconds,
            max_retries=profile.max_retries,
            retry_base_seconds=profile.retry_base_seconds,
            retry_max_seconds=profile.retry_max_seconds,
            retry_jitter_fraction=profile.retry_jitter_fraction,
        )
        return OpenAITranslationProvider(
            generation_provider=generation,
            model_name=_normalize_openai_compatible_model(profile.model),
            provider_name="openai",
        )
    raise ProviderNotConfiguredError(
        f"translation provider {profile.provider!r} is not registered"
    )


def build_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    for capability in ("generation", "embedding", "translation"):
        for provider_name in ("openrouter", "openai"):
            if capability == "generation":
                factory = partial(_build_generation, provider_name)
            elif capability == "embedding":
                factory = partial(_build_embedding, provider_name)
            else:
                factory = partial(_build_translation, provider_name)
            registry.register(
                ProviderDefinition(
                    name=provider_name,
                    capability=capability,
                    factory=factory,
                )
            )
    return registry


def get_provider_registry() -> ProviderRegistry:
    return build_provider_registry()


def build_generation_provider(
    profile: GenerationProfile | None = None,
) -> Any:
    registry = get_provider_registry()
    requested = profile.provider if profile is not None else None
    return cast(
        Any,
        registry.resolve("generation", requested=requested, config=profile),
    )


def build_embedding_provider(
    profile: EmbeddingProfile | None = None,
) -> Any:
    registry = get_provider_registry()
    requested = profile.provider if profile is not None else None
    return cast(
        Any,
        registry.resolve("embedding", requested=requested, config=profile),
    )


def build_translation_provider(profile: TranslationProfile) -> Any:
    registry = get_provider_registry()
    return cast(
        Any,
        registry.resolve("translation", requested=profile.provider, config=profile),
    )
