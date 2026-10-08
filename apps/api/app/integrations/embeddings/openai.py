"""OpenAI embedding provider (text-embedding-3-*).

Uses ``tiktoken`` for real token counting. If the tokenizer is
unavailable for the configured model, ``estimate_input_tokens``
returns ``None`` and pre-flight validation is skipped; the provider's
HTTP 400 response becomes authoritative.
"""
from __future__ import annotations

import logging
import math
import random
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import get_settings
from app.domain.embeddings import (
    EmbeddingBatchResult,
    EmbeddingProfile,
    EmbeddingUsage,
)
from app.integrations.embeddings.base import (
    EmbeddingAuthenticationError,
    EmbeddingInputTooLargeError,
    EmbeddingInvalidRequestError,
    EmbeddingInvalidResponseError,
    EmbeddingProviderUnavailableError,
    EmbeddingRateLimitError,
)

if TYPE_CHECKING:
    from tiktoken import Encoding
logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}

# OpenAI documented limits for text-embedding-3-*:
_MAX_BATCH_SIZE = 2048
_MAX_TOKENS_PER_ITEM = 8191
_MAX_TOKENS_PER_REQUEST = 300_000


class OpenAIEmbeddingProvider:
    provider_name: str = "openai"
    max_batch_size: int = _MAX_BATCH_SIZE
    max_input_tokens_per_item: int | None = _MAX_TOKENS_PER_ITEM
    max_input_tokens_per_request: int | None = _MAX_TOKENS_PER_REQUEST

    def __init__(
        self,
        *,
        profile: EmbeddingProfile,
        api_key: str | None = None,
        base_url: str | None = None,
        provider_name: str = "openai",
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_base_seconds: float | None = None,
        retry_max_seconds: float | None = None,
        retry_jitter_fraction: float | None = None,
        _sleep=time.sleep,
        _random=random.random,
    ) -> None:
        settings = get_settings()
        self._profile = profile
        self.provider_name = provider_name
        self.model_name = profile.model
        self.dimensions = profile.dimensions
        self._base_url = (
            base_url or settings.embedding_openai_base_url
        ).rstrip("/")
        self._api_key = api_key or settings.embedding_openai_api_key
        self._timeout = float(
            timeout_seconds
            if timeout_seconds is not None
            else settings.embedding_timeout_seconds
        )
        self._max_retries = (
            max_retries
            if max_retries is not None
            else settings.embedding_max_retries
        )
        self._retry_base = float(
            retry_base_seconds
            if retry_base_seconds is not None
            else settings.embedding_retry_base_seconds
        )
        self._retry_max = float(
            retry_max_seconds
            if retry_max_seconds is not None
            else settings.embedding_retry_max_seconds
        )
        self._jitter_fraction = float(
            retry_jitter_fraction
            if retry_jitter_fraction is not None
            else settings.embedding_retry_jitter_fraction
        )
        self._sleep = _sleep
        self._random = _random
        self._encoding = _load_tiktoken_encoding(profile.model)

    # ------------------------------------------------------------------
    def estimate_input_tokens(self, text: str) -> int | None:
        if self._encoding is None:
            return None
        if not text:
            return 0
        return len(self._encoding.encode(text))

    # ------------------------------------------------------------------
    def embed_documents(
        self, texts: Sequence[str]
    ) -> EmbeddingBatchResult:
        return self._embed(list(texts))

    def embed_query(self, text: str) -> list[float]:
        result = self._embed([text])
        return result.vectors[0]

    # ------------------------------------------------------------------
    def _embed(self, texts: list[str]) -> EmbeddingBatchResult:
        if not texts:
            raise EmbeddingInvalidRequestError("empty input batch")

        if self._encoding is not None:
            for idx, t in enumerate(texts):
                count = self.estimate_input_tokens(t) or 0
                if count > _MAX_TOKENS_PER_ITEM:
                    raise EmbeddingInputTooLargeError(
                        f"item {idx} exceeds "
                        f"{_MAX_TOKENS_PER_ITEM} tokens"
                    )

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._embed_once(texts)
            except (
                EmbeddingRateLimitError,
                EmbeddingProviderUnavailableError,
            ) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                self._sleep(self._compute_delay(attempt))
                logger.warning(
                    "embedding_retry provider=%s attempt=%d",
                    self.provider_name,
                    attempt + 1,
                )

        assert last_error is not None
        raise last_error

    def _compute_delay(self, attempt: int) -> float:
        base = min(self._retry_max, self._retry_base * (2 ** attempt))
        jitter = base * self._jitter_fraction * self._random()
        return min(self._retry_max, base + jitter)

    def _embed_once(self, texts: list[str]) -> EmbeddingBatchResult:
        if not self._api_key:
            raise EmbeddingAuthenticationError(
                f"{self.provider_name} API key is not configured"
            )

        payload: dict[str, Any] = {
            "input": texts,
            "model": self._profile.model,
            "encoding_format": "float",
        }
        if self._profile.model.startswith("text-embedding-3"):
            payload["dimensions"] = self._profile.dimensions

        try:
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            settings = get_settings()
            if self.provider_name == "openrouter":
                if settings.openrouter_http_referer.strip():
                    headers["HTTP-Referer"] = settings.openrouter_http_referer.strip()
                if settings.openrouter_app_title.strip():
                    headers["X-Title"] = settings.openrouter_app_title.strip()
            response = httpx.post(
                f"{self._base_url}/embeddings",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise EmbeddingProviderUnavailableError("timeout") from exc
        except httpx.HTTPError as exc:
            raise EmbeddingProviderUnavailableError(
                f"transport: {type(exc).__name__}"
            ) from exc

        if response.status_code in _RETRYABLE_STATUSES:
            if response.status_code == 429:
                raise EmbeddingRateLimitError(
                    f"HTTP {response.status_code}"
                )
            raise EmbeddingProviderUnavailableError(
                f"HTTP {response.status_code}"
            )
        if response.status_code in (401, 403):
            raise EmbeddingAuthenticationError(
                f"HTTP {response.status_code}"
            )
        if response.status_code == 400:
            raise EmbeddingInvalidRequestError("HTTP 400")
        if response.status_code >= 400:
            raise EmbeddingInvalidRequestError(
                f"HTTP {response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise EmbeddingInvalidResponseError("invalid JSON") from exc

        data = body.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise EmbeddingInvalidResponseError("data length mismatch")

        ordered: list[list[float] | None] = [None] * len(texts)
        for item in data:
            if not isinstance(item, dict):
                raise EmbeddingInvalidResponseError("item not object")
            idx = item.get("index")
            emb = item.get("embedding")
            if (
                not isinstance(idx, int)
                or idx < 0
                or idx >= len(texts)
                or not isinstance(emb, list)
            ):
                raise EmbeddingInvalidResponseError("malformed item")
            ordered[idx] = [float(v) for v in emb]

        if any(v is None for v in ordered):
            raise EmbeddingInvalidResponseError("missing vectors")

        vectors: list[list[float]] = []
        for v in ordered:
            assert v is not None
            _validate_vector(v, self._profile.dimensions)
            vectors.append(v)

        usage_raw = body.get("usage") or {}
        input_tokens = int(usage_raw.get("prompt_tokens", 0))
        if input_tokens < 0:
            raise EmbeddingInvalidResponseError("negative usage")
        usage = EmbeddingUsage(
            input_tokens=input_tokens, request_count=1
        )

        return EmbeddingBatchResult(
            vectors=vectors,
            usage=usage,
            provider_request_id=response.headers.get("x-request-id"),
        )


def _load_tiktoken_encoding(model: str) -> Encoding | None:
    try:
        import tiktoken
    except ImportError:  # pragma: no cover
        logger.warning(
            "tiktoken not installed; token counting skipped"
        )
        return None
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        logger.info("no tiktoken encoding for model=%s", model)
        return None


def _validate_vector(v: list[float], dimensions: int) -> None:
    if len(v) != dimensions:
        raise EmbeddingInvalidResponseError(
            f"expected {dimensions} dims, got {len(v)}"
        )
    if not any(abs(x) > 0.0 for x in v):
        raise EmbeddingInvalidResponseError("zero vector")
    for x in v:
        if not math.isfinite(x):
            raise EmbeddingInvalidResponseError("non-finite")


__all__ = ["OpenAIEmbeddingProvider"]
