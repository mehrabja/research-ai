"""Sapling AI Detector integration."""
from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.core.config import get_settings
from app.domain.detection import DetectionProviderResult
from app.integrations.detection.base import (
    DetectionAuthenticationError,
    DetectionInputTooLargeError,
    DetectionInvalidRequestError,
    DetectionInvalidResponseError,
    DetectionProviderUnavailableError,
    DetectionQuotaExceededError,
    DetectionRateLimitError,
    DetectionTimeoutError,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}


class SaplingDetectionProvider:
    """Server-side adapter for Sapling's AI Detector API."""

    provider_name = "sapling"

    def __init__(
        self,
        *,
        _sleep: Callable[[float], None] = time.sleep,
        _random: Callable[[], float] = random.random,
    ) -> None:
        settings = get_settings()
        self._base_url = settings.detection_sapling_base_url.rstrip("/")
        self.model_name = settings.detection_sapling_model
        self._key = settings.sapling_api_key
        self._timeout = float(settings.detection_timeout_seconds)
        self._max_chars = min(int(settings.detection_max_input_chars), 200_000)
        self._max_retries = int(settings.detection_max_retries)
        self._retry_base = float(settings.detection_retry_base_seconds)
        self._retry_max = float(settings.detection_retry_max_seconds)
        self._jitter = float(settings.detection_retry_jitter_fraction)
        self._sleep = _sleep
        self._random = _random

    def detect(self, *, text: str) -> DetectionProviderResult:
        if not self._base_url:
            raise DetectionProviderUnavailableError(
                "Sapling detection endpoint is not configured"
            )
        if not self._key:
            raise DetectionAuthenticationError(
                "Sapling API key is not configured"
            )
        if len(text) > self._max_chars:
            raise DetectionInputTooLargeError(
                "text exceeds the configured Sapling input limit"
            )

        last_error: (
            DetectionRateLimitError
            | DetectionProviderUnavailableError
            | DetectionTimeoutError
            | None
        ) = None

        for attempt in range(self._max_retries + 1):
            try:
                return self._detect_once(text=text)
            except (
                DetectionRateLimitError,
                DetectionProviderUnavailableError,
                DetectionTimeoutError,
            ) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                delay = self._compute_delay(
                    attempt=attempt,
                    retry_after=(
                        exc.retry_after
                        if isinstance(exc, DetectionRateLimitError)
                        else None
                    ),
                )
                self._sleep(delay)
                logger.warning(
                    "sapling_detection_retry attempt=%d provider=%s",
                    attempt + 1,
                    self.provider_name,
                )

        assert last_error is not None
        raise last_error

    def _compute_delay(
        self,
        *,
        attempt: int,
        retry_after: float | None,
    ) -> float:
        if retry_after is not None:
            return min(self._retry_max, max(0.0, retry_after))
        base = min(self._retry_max, self._retry_base * (2**attempt))
        jitter = base * self._jitter * self._random()
        return min(self._retry_max, base + jitter)

    def _detect_once(self, *, text: str) -> DetectionProviderResult:
        try:
            response = httpx.post(
                self._base_url + "/aidetect",
                json={
                    "text": text,
                    "sent_scores": True,
                    "version": self.model_name,
                },
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._key}",
                },
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise DetectionTimeoutError(
                "Sapling request timed out"
            ) from exc
        except httpx.HTTPError as exc:
            raise DetectionProviderUnavailableError(
                "Sapling transport failed"
            ) from exc

        if response.status_code in (401, 403):
            raise DetectionAuthenticationError(
                f"Sapling authentication failed: HTTP {response.status_code}"
            )
        if response.status_code in (402, 429):
            if response.status_code == 402:
                raise DetectionQuotaExceededError(
                    "Sapling account has insufficient quota"
                )
            raise DetectionRateLimitError(
                f"Sapling rate limited request: HTTP {response.status_code}",
                retry_after=_parse_retry_after(
                    response.headers.get("Retry-After")
                ),
            )
        if response.status_code == 413:
            raise DetectionInputTooLargeError(
                "Sapling rejected the request as too large"
            )
        if response.status_code in _RETRYABLE_STATUSES:
            raise DetectionProviderUnavailableError(
                f"Sapling server error: HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            raise DetectionInvalidRequestError(
                f"Sapling rejected request: HTTP {response.status_code}"
            )

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise DetectionInvalidResponseError(
                "Sapling returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise DetectionInvalidResponseError(
                "Sapling response must be an object"
            )

        score = payload.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise DetectionInvalidResponseError(
                "Sapling response is missing numeric score"
            )
        probability = float(score)
        if not 0.0 <= probability <= 1.0:
            raise DetectionInvalidResponseError(
                "Sapling score must be between 0 and 1"
            )

        sentence_scores = payload.get("sentence_scores")
        if not isinstance(sentence_scores, list):
            sentence_scores = []

        details: dict[str, object] = {
            "sentence_scores": sentence_scores,
        }

        return DetectionProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            probability=probability,
            raw_label=None,
            details=details,
            input_chars=len(text),
        )


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


__all__ = ["SaplingDetectionProvider"]
