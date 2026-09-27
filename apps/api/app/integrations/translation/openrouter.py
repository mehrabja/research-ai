"""OpenRouter translation adapter built on the common translation contract."""
from __future__ import annotations

from app.integrations.translation.openai import OpenAITranslationProvider


class OpenRouterTranslationProvider(OpenAITranslationProvider):
    provider_name = "openrouter"
