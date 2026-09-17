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
    from app.core.config import get_settings
    from app.integrations.generation.openai import OpenAIGenerationProvider
    from app.integrations.translation.openai import OpenAITranslationProvider

    s = get_settings()
    if profile.provider != "openai":
        raise ValueError(
            f"unsupported translation provider {profile.provider!r}"
        )

    gen_provider = OpenAIGenerationProvider(
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
        generation_provider=gen_provider,
        model_name=profile.model,
    )
