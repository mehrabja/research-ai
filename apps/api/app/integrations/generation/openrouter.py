"""OpenRouter generation provider using the OpenAI-compatible API."""
from __future__ import annotations

from app.core.config import get_settings
from app.integrations.generation.openai import OpenAIGenerationProvider


class OpenRouterGenerationProvider(OpenAIGenerationProvider):
    provider_name = "openrouter"

    def __init__(self, *, model: str) -> None:
        settings = get_settings()
        super().__init__(
            model=model,
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            timeout_seconds=settings.generation_timeout_seconds,
            max_retries=settings.generation_max_retries,
            retry_base_seconds=settings.generation_retry_base_seconds,
            retry_max_seconds=settings.generation_retry_max_seconds,
            retry_jitter_fraction=settings.generation_retry_jitter_fraction,
        )
