from __future__ import annotations

from app.integrations.generation.base import GenerationProviderUnavailableError
from app.services.provider_registry import GenerationProviderFallback


class Result:
    provider = "backup"
    model = "backup-model"


class Primary:
    provider_name = "primary"
    model_name = "primary-model"

    def generate(self, **kwargs):
        raise GenerationProviderUnavailableError("down")


class Backup:
    provider_name = "backup"
    model_name = "backup-model"

    def generate(self, **kwargs):
        return Result()


def test_generation_fallback_uses_next_provider() -> None:
    router = GenerationProviderFallback((Primary(), Backup()))
    result = router.generate(
        system_prompt="system",
        user_prompt="user",
        temperature=0.2,
        max_output_tokens=20,
    )
    assert result.provider == "backup"
    assert router.attempted_providers == ["primary", "backup"]
    assert router.last_used_provider_name == "backup"
