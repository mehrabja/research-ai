"""M39 capability-aware provider registry and deterministic resolver."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

from app.core.exceptions import AppError
from app.services.generation_profile import get_current_generation_profile
from app.services.embedding_profile import get_current_embedding_profile
from app.services.detection_profile import get_current_detection_profile
from app.services.translation_profile import get_current_translation_profile

class ProviderResolutionError(AppError):
    code="PROVIDER_RESOLUTION_FAILED"
    status_code=503
    message="No configured provider is available for the requested capability."

@dataclass(frozen=True)
class ProviderDecision:
    capability: str
    provider: str
    model: str
    fallback_provider: str | None
    policy_version: str

def _resolve(name: str, factory: Callable[[], Any]) -> Any:
    try:
        return factory()
    except Exception as exc:
        raise ProviderResolutionError(
            f"provider {name!r} could not be initialized"
        ) from exc

def generation_provider() -> tuple[Any, ProviderDecision]:
    p=get_current_generation_profile()
    if p.provider!="openai":
        raise ProviderResolutionError(f"unsupported generation provider {p.provider!r}")
    from app.integrations.generation.openai import OpenAIGenerationProvider
    return _resolve("openai",lambda:OpenAIGenerationProvider(model=p.model)), ProviderDecision("text_generation",p.provider,p.model,None,p.profile_version)

def embedding_provider() -> tuple[Any, ProviderDecision]:
    p=get_current_embedding_profile()
    if p.provider!="openai":
        raise ProviderResolutionError(f"unsupported embedding provider {p.provider!r}")
    from app.integrations.embeddings.openai import OpenAIEmbeddingProvider
    return _resolve("openai",lambda:OpenAIEmbeddingProvider(profile=p)), ProviderDecision("embedding",p.provider,p.model,None,p.profile_version)

def detection_provider() -> tuple[Any, ProviderDecision]:
    p=get_current_detection_profile()
    if p.provider!="heuristic":
        raise ProviderResolutionError(f"unsupported detection provider {p.provider!r}")
    from app.integrations.detection.heuristic import HeuristicDetectionProvider
    return HeuristicDetectionProvider(), ProviderDecision("ai_detection",p.provider,p.model,None,p.profile_version)

def translation_provider() -> tuple[Any, ProviderDecision]:
    p=get_current_translation_profile()
    from app.services.translation_profile import build_translation_provider
    return _resolve(p.provider,lambda:build_translation_provider(p)), ProviderDecision("translation",p.provider,p.model,None,p.profile_version)
