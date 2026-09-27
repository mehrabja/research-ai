"""M16 — Translation profile + provider factory."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class TranslationProfile:
    provider: str
    model: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    max_retries: int
    retry_base_seconds: float
    retry_max_seconds: float
    retry_jitter_fraction: float
    max_input_chars: int
    max_output_chars: int
    preservation_retry_count: int
    profile_version: str

    @property
    def profile_id(self) -> str:
        return f"{self.provider}/{self.model}:{self.profile_version}"


def get_current_translation_profile() -> TranslationProfile:
    s = get_settings()
    return TranslationProfile(
        provider=s.translation_provider,
        model=s.translation_model,
        temperature=s.translation_temperature,
        max_output_tokens=s.translation_max_output_tokens,
        timeout_seconds=s.translation_timeout_seconds,
        max_retries=s.translation_max_retries,
        retry_base_seconds=s.translation_retry_base_seconds,
        retry_max_seconds=s.translation_retry_max_seconds,
        retry_jitter_fraction=s.translation_retry_jitter_fraction,
        max_input_chars=s.translation_max_input_chars,
        max_output_chars=s.translation_max_output_chars,
        preservation_retry_count=s.translation_preservation_retry_count,
        profile_version=s.translation_profile_version,
    )


def get_current_translation_profile_id() -> str:
    return get_current_translation_profile().profile_id


def build_translation_provider(profile: TranslationProfile):
    from app.services.provider_registry import (
        build_translation_provider as build_registry_translation_provider,
    )

    return build_registry_translation_provider(profile)
