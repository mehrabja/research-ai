"""Shared constructor for the current generation profile + provider."""
from __future__ import annotations

from app.core.config import get_settings
from app.domain.generation import (
    GenerationProfile,
    build_generation_profile_id,
)
from app.integrations.generation.base import GenerationProvider
from app.services.provider_registry import build_generation_provider as build_registry_generation_provider


def get_current_generation_profile() -> GenerationProfile:
    s = get_settings()
    return GenerationProfile(
        provider=s.generation_provider,
        model=s.generation_model,
        temperature=s.generation_temperature,
        max_output_tokens=s.generation_max_output_tokens,
        profile_version=s.generation_profile_version,
    )


def get_current_generation_profile_id() -> str:
    return build_generation_profile_id(get_current_generation_profile())


def build_generation_provider(
    profile: GenerationProfile | None = None,
) -> GenerationProvider:
    return build_registry_generation_provider(
        profile or get_current_generation_profile()
    )


__all__ = [
    "build_generation_provider",
    "get_current_generation_profile",
    "get_current_generation_profile_id",
]
