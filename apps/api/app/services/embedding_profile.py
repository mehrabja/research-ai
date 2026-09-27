"""Single source of truth for the current embedding profile + provider.

Both M9 routes and the M11 worker construct the profile and provider
through this module, so a config change cannot silently diverge.

Construction only — no provider HTTP happens here.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.domain.embeddings import (
    EmbeddingProfile,
    build_embedding_profile_id,
)
from app.integrations.embeddings.base import EmbeddingProvider
from app.providers.registry import ProviderCapability, ProviderContext, resolve_provider


def get_current_embedding_profile() -> EmbeddingProfile:
    s = get_settings()
    return EmbeddingProfile(
        provider=s.embedding_provider,
        model=s.embedding_model,
        dimensions=s.embedding_dimensions,
        distance_metric=s.embedding_distance_metric,  # type: ignore[arg-type]
        profile_version=s.embedding_profile_version,
    )


def get_current_embedding_profile_id() -> str:
    return build_embedding_profile_id(get_current_embedding_profile())


def build_embedding_provider(
    profile: EmbeddingProfile | None = None,
) -> EmbeddingProvider:
    p = profile or get_current_embedding_profile()
    return resolve_provider(
        capability=ProviderCapability.EMBEDDING,
        preferred=p.provider,
        context=ProviderContext(profile=p),
    )


__all__ = [
    "build_embedding_provider",
    "get_current_embedding_profile",
    "get_current_embedding_profile_id",
]
