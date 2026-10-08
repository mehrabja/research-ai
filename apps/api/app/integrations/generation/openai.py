"""OpenAI chat completions adapter (httpx, no SDK)."""
from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.domain.generation import GenerationProviderResult
from app.integrations.generation.base import (
    GenerationAuthenticationError,
    GenerationInvalidRequestError,
    GenerationInvalidResponseError,
    GenerationProviderUnavailableError,
    GenerationRateLimitError,
    GenerationTimeoutError,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}


class OpenAIGenerationProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        model: str,
        base_url: str | None = None,
        provider_name: str = "openai",
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_base_seconds: float | None = None,
        retry_max_seconds: float | None = None,
        retry_jitter_fraction: float | None = None,
        _sleep=time.sleep,
        _random=random.random,
    ) -> None:
        s = get_settings()
        self.model_name = model
        self.provider_name = provider_name
        self._base_url = (
            base_url or s.generation_openai_base_url
        ).rstrip("/")
        self._api_key = api_key or s.generation_openai_api_key
        self._timeout = float(
            timeout_seconds if timeout_seconds is not None
            else s.generation_timeout_seconds
        )
        self._max_retries = (
            max_retries if max_retries is not None
            else s.generation_max_retries
        )
        self._retry_base = float(
            retry_base_seconds if retry_base_seconds is not None
            else s.generation_retry_base_seconds
        )
        self._retry_max = float(
            retry_max_seconds if retry_max_seconds is not None
            else s.generation_retry_max_seconds
        )
        self._jitter = float(
            retry_jitter_fraction if retry_jitter_fraction is not None
            else s.generation_retry_jitter_fraction
        )
        self._sleep = _sleep
        self._random = _random

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> GenerationProviderResult:
        if not system_prompt or not user_prompt:
            raise GenerationInvalidRequestError("empty prompt")

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._generate_once(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
            except (
                GenerationRateLimitError,
                GenerationProviderUnavailableError,
            ) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                self._sleep(self._compute_delay(attempt))
                logger.warning(
                    "generation_retry attempt=%d", attempt + 1
                )
        assert last_error is not None
        raise last_error

    def _compute_delay(self, attempt: int) -> float:
        base = min(self._retry_max, self._retry_base * (2 ** attempt))
        jitter = base * self._jitter * self._random()
        return min(self._retry_max, base + jitter)

    def _generate_once(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
    ) -> GenerationProviderResult:
        if not self._api_key:
            raise GenerationAuthenticationError(
                f"{self.provider_name} API key is not configured"
            )

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise GenerationTimeoutError("timeout") from exc
        except httpx.HTTPError as exc:
            raise GenerationProviderUnavailableError(
                f"transport: {type(exc).__name__}"
            ) from exc

        if response.status_code in _RETRYABLE_STATUSES:
            if response.status_code == 429:
                raise GenerationRateLimitError(
                    f"HTTP {response.status_code}"
                )
            raise GenerationProviderUnavailableError(
                f"HTTP {response.status_code}"
            )
        if response.status_code in (401, 403):
            raise GenerationAuthenticationError(
                f"HTTP {response.status_code}"
            )
        if response.status_code == 400:
            raise GenerationInvalidRequestError("HTTP 400")
        if response.status_code >= 400:
            raise GenerationInvalidRequestError(
                f"HTTP {response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise GenerationInvalidResponseError("invalid JSON") from exc

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise GenerationInvalidResponseError("no choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise GenerationInvalidResponseError("malformed choice")
        message = first.get("message")
        if not isinstance(message, dict):
            raise GenerationInvalidResponseError("no message")
        text = message.get("content")
        if not isinstance(text, str):
            raise GenerationInvalidResponseError("no text content")

        usage_raw = body.get("usage") or {}
        return GenerationProviderResult(
            text=text,
            provider=self.provider_name,
            model=self.model_name,
            input_tokens=_as_int(usage_raw.get("prompt_tokens")),
            output_tokens=_as_int(usage_raw.get("completion_tokens")),
            total_tokens=_as_int(usage_raw.get("total_tokens")),
            request_id=response.headers.get("x-request-id"),
        )


def _as_int(v: object) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        n = int(v)
        return n if n >= 0 else None
    return None


__all__ = ["OpenAIGenerationProvider"]
