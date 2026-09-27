"""OpenRouter embeddings provider using the OpenAI-compatible endpoint."""
from __future__ import annotations

from app.core.config import get_settings
from app.domain.embeddings import EmbeddingProfile
from app.integrations.embeddings.openai import OpenAIEmbeddingProvider


class OpenRouterEmbeddingProvider(OpenAIEmbeddingProvider):
    provider_name = "openrouter"

    def __init__(self, profile: EmbeddingProfile) -> None:
        settings = get_settings()
        super().__init__(
            profile=profile,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            timeout_seconds=settings.embedding_timeout_seconds,
            max_retries=settings.embedding_max_retries,
            retry_base_seconds=settings.embedding_retry_base_seconds,
            retry_max_seconds=settings.embedding_retry_max_seconds,
            retry_jitter_fraction=settings.embedding_retry_jitter_fraction,
        )
