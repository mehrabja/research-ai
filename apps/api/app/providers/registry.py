"""Central provider registry and deterministic routing."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import AppError


class ProviderCapability(StrEnum):
    GENERATION = "generation"
    EMBEDDING = "embedding"
    TRANSLATION = "translation"
    DETECTION = "detection"
    SOURCE_DISCOVERY = "source_discovery"
    BILLING = "billing"
    EMAIL = "email"
    STORAGE = "storage"


@dataclass(frozen=True)
class ProviderContext:
    """Optional execution context passed to provider factories."""

    profile: Any | None = None


ProviderFactory = Callable[[ProviderContext], Any]


@dataclass(frozen=True)
class ProviderSpec:
    capability: ProviderCapability
    name: str
    factory: ProviderFactory


class ProviderResolutionError(AppError):
    """Raised when no configured provider can satisfy a capability."""

    def __init__(
        self,
        *,
        capability: ProviderCapability,
        attempted: tuple[str, ...],
    ) -> None:
        self.capability = capability
        self.attempted = attempted
        names = ", ".join(attempted) or "<none>"
        super().__init__(
            f"No provider is registered for capability "
            f"{capability.value!r}; attempted: {names}",
            code="PROVIDER_UNAVAILABLE",
        )
        self.status_code = 503


class ProviderRegistry:
    """In-process registry with explicit, ordered provider routing."""

    def __init__(self) -> None:
        self._specs: dict[ProviderCapability, dict[str, ProviderSpec]] = {}

    def register(
        self,
        *,
        capability: ProviderCapability,
        name: str,
        factory: ProviderFactory,
    ) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("provider name must not be empty")
        self._specs.setdefault(capability, {})[normalized] = ProviderSpec(
            capability=capability,
            name=normalized,
            factory=factory,
        )

    def providers(self, capability: ProviderCapability) -> tuple[str, ...]:
        return tuple(sorted(self._specs.get(capability, {}).keys()))

    def resolve_chain(
        self,
        *,
        capability: ProviderCapability,
        preferred: str,
        fallbacks: Iterable[str] = (),
        context: ProviderContext | None = None,
    ) -> tuple[Any, ...]:
        names: list[str] = []
        for raw in (preferred, *fallbacks):
            name = str(raw).strip().lower()
            if name and name not in names:
                names.append(name)

        context = context or ProviderContext()
        resolved: list[Any] = []
        attempted: list[str] = []
        for name in names:
            attempted.append(name)
            spec = self._specs.get(capability, {}).get(name)
            if spec is None:
                continue
            resolved.append(spec.factory(context))

        if not resolved:
            raise ProviderResolutionError(
                capability=capability,
                attempted=tuple(attempted),
            )
        return tuple(resolved)

    def resolve(
        self,
        *,
        capability: ProviderCapability,
        preferred: str,
        fallbacks: Iterable[str] = (),
        context: ProviderContext | None = None,
    ) -> Any:
        return self.resolve_chain(
            capability=capability,
            preferred=preferred,
            fallbacks=fallbacks,
            context=context,
        )[0]


def _configured_fallbacks(capability: ProviderCapability) -> tuple[str, ...]:
    raw = getattr(get_settings(), "provider_fallbacks", "")
    if not raw:
        return ()
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        key, values = entry.split("=", 1)
        if key.strip().lower() != capability.value:
            continue
        return tuple(item.strip() for item in values.split(",") if item.strip())
    return ()


def build_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()

    def generation_factory(ctx: ProviderContext) -> Any:
        from app.domain.generation import GenerationProfile
        from app.integrations.generation.openai import OpenAIGenerationProvider

        profile = ctx.profile
        if profile is None:
            from app.services.generation_profile import get_current_generation_profile
            profile = get_current_generation_profile()
        if not isinstance(profile, GenerationProfile):
            raise TypeError("generation provider requires GenerationProfile")
        return OpenAIGenerationProvider(model=profile.model)

    def openrouter_generation_factory(ctx: ProviderContext) -> Any:
        from app.domain.generation import GenerationProfile
        from app.integrations.generation.openrouter import OpenRouterGenerationProvider

        profile = ctx.profile
        if profile is None:
            from app.services.generation_profile import get_current_generation_profile
            profile = get_current_generation_profile()
        if not isinstance(profile, GenerationProfile):
            raise TypeError("generation provider requires GenerationProfile")
        return OpenRouterGenerationProvider(model=profile.model)

    def embedding_factory(ctx: ProviderContext) -> Any:
        from app.domain.embeddings import EmbeddingProfile
        from app.integrations.embeddings.openai import OpenAIEmbeddingProvider

        profile = ctx.profile
        if profile is None:
            from app.services.embedding_profile import get_current_embedding_profile
            profile = get_current_embedding_profile()
        if not isinstance(profile, EmbeddingProfile):
            raise TypeError("embedding provider requires EmbeddingProfile")
        return OpenAIEmbeddingProvider(profile)

    def openrouter_embedding_factory(ctx: ProviderContext) -> Any:
        from app.domain.embeddings import EmbeddingProfile
        from app.integrations.embeddings.openrouter import OpenRouterEmbeddingProvider

        profile = ctx.profile
        if profile is None:
            from app.services.embedding_profile import get_current_embedding_profile
            profile = get_current_embedding_profile()
        if not isinstance(profile, EmbeddingProfile):
            raise TypeError("embedding provider requires EmbeddingProfile")
        return OpenRouterEmbeddingProvider(profile)

    def translation_factory(ctx: ProviderContext) -> Any:
        from app.services.translation_profile import TranslationProfile
        from app.integrations.generation.openai import OpenAIGenerationProvider
        from app.integrations.translation.openai import OpenAITranslationProvider

        profile = ctx.profile
        if profile is None:
            from app.services.translation_profile import get_current_translation_profile
            profile = get_current_translation_profile()
        if not isinstance(profile, TranslationProfile):
            raise TypeError("translation provider requires TranslationProfile")

        settings = get_settings()
        generation = OpenAIGenerationProvider(
            model=profile.model,
            base_url=settings.generation_openai_base_url or None,
            api_key=settings.generation_openai_api_key or None,
            timeout_seconds=profile.timeout_seconds,
            retry_base_seconds=profile.retry_base_seconds,
            retry_max_seconds=profile.retry_max_seconds,
            retry_jitter_fraction=profile.retry_jitter_fraction,
        )
        return OpenAITranslationProvider(
            generation_provider=generation,
            model_name=profile.model,
        )

    def openrouter_translation_factory(ctx: ProviderContext) -> Any:
        from app.services.translation_profile import TranslationProfile
        from app.integrations.generation.openrouter import OpenRouterGenerationProvider
        from app.integrations.translation.openrouter import OpenRouterTranslationProvider

        profile = ctx.profile
        if profile is None:
            from app.services.translation_profile import get_current_translation_profile
            profile = get_current_translation_profile()
        if not isinstance(profile, TranslationProfile):
            raise TypeError("translation provider requires TranslationProfile")
        return OpenRouterTranslationProvider(
            generation_provider=OpenRouterGenerationProvider(model=profile.model),
            model_name=profile.model,
        )

    def detection_factory(ctx: ProviderContext) -> Any:
        from app.integrations.detection.heuristic import HeuristicDetectionProvider
        return HeuristicDetectionProvider()

    def http_detection_factory(ctx: ProviderContext) -> Any:
        from app.integrations.detection.http import HTTPDetectionProvider
        return HTTPDetectionProvider()

    def source_factory(ctx: ProviderContext) -> Any:
        from app.integrations.sources.semantic_scholar import SemanticScholarProvider
        settings = get_settings()
        return SemanticScholarProvider(
            api_key=settings.semantic_scholar_api_key,
            timeout_seconds=settings.semantic_scholar_timeout_seconds,
        )

    def openalex_factory(ctx: ProviderContext) -> Any:
        from app.integrations.sources.openalex import OpenAlexProvider
        return OpenAlexProvider()

    def crossref_factory(ctx: ProviderContext) -> Any:
        from app.integrations.sources.crossref import CrossrefProvider
        return CrossrefProvider()

    def noop_email_factory(ctx: ProviderContext) -> Any:
        from app.email.noop import NoopEmailProvider
        return NoopEmailProvider()

    def resend_email_factory(ctx: ProviderContext) -> Any:
        from app.email.resend import ResendEmailProvider
        return ResendEmailProvider()

    def local_storage_factory(ctx: ProviderContext) -> Any:
        from pathlib import Path
        from app.core.config import REPO_ROOT
        from app.services.file_storage import LocalStorageProvider
        settings = get_settings()
        root = Path(settings.file_storage_local_root)
        if not root.is_absolute():
            root = REPO_ROOT / "apps" / "api" / root
        return LocalStorageProvider(root)

    def s3_storage_factory(ctx: ProviderContext) -> Any:
        from app.services.s3_storage import build_s3_storage_provider
        return build_s3_storage_provider()

    def billing_factory(ctx: ProviderContext) -> Any:
        from app.billing.fake import FakeBillingProvider
        return FakeBillingProvider()

    def stripe_billing_factory(ctx: ProviderContext) -> Any:
        from app.billing.stripe import StripeBillingProvider
        return StripeBillingProvider()

    registry.register(
        capability=ProviderCapability.GENERATION,
        name="openai",
        factory=generation_factory,
    )
    registry.register(
        capability=ProviderCapability.EMBEDDING,
        name="openai",
        factory=embedding_factory,
    )
    registry.register(
        capability=ProviderCapability.GENERATION,
        name="openrouter",
        factory=openrouter_generation_factory,
    )
    registry.register(
        capability=ProviderCapability.EMBEDDING,
        name="openrouter",
        factory=openrouter_embedding_factory,
    )
    registry.register(
        capability=ProviderCapability.TRANSLATION,
        name="openai",
        factory=translation_factory,
    )
    registry.register(
        capability=ProviderCapability.TRANSLATION,
        name="openrouter",
        factory=openrouter_translation_factory,
    )
    registry.register(
        capability=ProviderCapability.DETECTION,
        name="heuristic",
        factory=detection_factory,
    )
    registry.register(
        capability=ProviderCapability.DETECTION,
        name="http",
        factory=http_detection_factory,
    )
    registry.register(
        capability=ProviderCapability.SOURCE_DISCOVERY,
        name="semantic_scholar",
        factory=source_factory,
    )
    registry.register(
        capability=ProviderCapability.SOURCE_DISCOVERY,
        name="openalex",
        factory=openalex_factory,
    )
    registry.register(
        capability=ProviderCapability.SOURCE_DISCOVERY,
        name="crossref",
        factory=crossref_factory,
    )
    registry.register(
        capability=ProviderCapability.BILLING,
        name="fake",
        factory=billing_factory,
    )
    registry.register(
        capability=ProviderCapability.BILLING,
        name="stripe",
        factory=stripe_billing_factory,
    )
    registry.register(
        capability=ProviderCapability.EMAIL,
        name="none",
        factory=noop_email_factory,
    )
    registry.register(
        capability=ProviderCapability.EMAIL,
        name="resend",
        factory=resend_email_factory,
    )
    registry.register(
        capability=ProviderCapability.STORAGE,
        name="local",
        factory=local_storage_factory,
    )
    registry.register(
        capability=ProviderCapability.STORAGE,
        name="s3",
        factory=s3_storage_factory,
    )
    return registry


_registry = build_default_registry()


def get_provider_registry() -> ProviderRegistry:
    return _registry


def resolve_provider(
    *,
    capability: ProviderCapability,
    preferred: str,
    fallbacks: Iterable[str] = (),
    context: ProviderContext | None = None,
) -> Any:
    configured = _configured_fallbacks(capability)
    chain = get_provider_registry().resolve_chain(
        capability=capability,
        preferred=preferred,
        fallbacks=tuple(fallbacks) + configured,
        context=context,
    )
    if len(chain) == 1:
        return chain[0]

    from app.providers.fallback import FallbackProvider
    return FallbackProvider(chain)


__all__ = [
    "ProviderCapability",
    "ProviderContext",
    "ProviderFactory",
    "ProviderRegistry",
    "ProviderResolutionError",
    "ProviderSpec",
    "build_default_registry",
    "get_provider_registry",
    "resolve_provider",
]
