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
    DetectionRateLimitError,
    DetectionTimeoutError,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}


class HTTPDetectionProvider:
    """Provider-neutral HTTP detector adapter.

    The endpoint accepts JSON {"text": "..."} and returns an object with
    "probability" plus optional "label" and "details".
    """

    provider_name = "http"

    def __init__(
        self,
        *,
        _sleep: Callable[[float], None] = time.sleep,
        _random: Callable[[], float] = random.random,
    ) -> None:
        settings = get_settings()
        self._url = settings.detection_api_base_url.rstrip("/")
        self.model_name = settings.detection_api_model
        self._key = settings.ai_detection_api_key
        self._timeout = float(settings.detection_timeout_seconds)
        self._max_chars = settings.detection_max_input_chars
        self._max_retries = settings.detection_max_retries
        self._retry_base = float(settings.detection_retry_base_seconds)
        self._retry_max = float(settings.detection_retry_max_seconds)
        self._jitter = float(settings.detection_retry_jitter_fraction)
        self._sleep = _sleep
        self._random = _random

    def detect(self, *, text: str) -> DetectionProviderResult:
        if not self._url:
            raise DetectionProviderUnavailableError(
                "detection endpoint is not configured"
            )
        if len(text) > self._max_chars:
            raise DetectionInputTooLargeError(
                "text exceeds detector input limit"
            )

        last_error: DetectionProviderUnavailableError | DetectionRateLimitError | DetectionTimeoutError | None = None
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
                self._sleep(self._compute_delay(attempt))
                logger.warning(
                    "detection_retry attempt=%d provider=%s",
                    attempt + 1,
                    self.provider_name,
                )
        assert last_error is not None
        raise last_error

    def _compute_delay(self, attempt: int) -> float:
        base = min(self._retry_max, self._retry_base * (2**attempt))
        jitter = base * self._jitter * self._random()
        return min(self._retry_max, base + jitter)

    def _detect_once(self, *, text: str) -> DetectionProviderResult:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        try:
            response = httpx.post(
                self._url,
                json={"text": text},
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise DetectionTimeoutError("detector request timed out") from exc
        except httpx.HTTPError as exc:
            raise DetectionProviderUnavailableError(
                "detector transport failed"
            ) from exc

        if response.status_code in (401, 403):
            raise DetectionAuthenticationError(
                "detector authentication failed"
            )
        if response.status_code in _RETRYABLE_STATUSES:
            if response.status_code == 429:
                raise DetectionRateLimitError(
                    f"detector rate limited request: HTTP {response.status_code}"
                )
            raise DetectionProviderUnavailableError(
                f"detector server error: {response.status_code}"
            )
        if response.status_code >= 400:
            raise DetectionInvalidRequestError(
                f"detector rejected request: {response.status_code}"
            )

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise DetectionInvalidResponseError(
                "detector returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise DetectionInvalidResponseError(
                "detector response must be an object"
            )

        probability = payload.get("probability")
        if probability is not None:
            try:
                probability = float(probability)
            except (TypeError, ValueError) as exc:
                raise DetectionInvalidResponseError(
                    "probability is not numeric"
                ) from exc
            if not 0.0 <= probability <= 1.0:
                raise DetectionInvalidResponseError(
                    "probability must be between 0 and 1"
                )

        label = payload.get("label", payload.get("raw_label"))
        if label is not None and not isinstance(label, str):
            label = None

        details = payload.get("details")
        if not isinstance(details, dict):
            details = {}

        return DetectionProviderResult(
            provider=self.provider_name,
            model=str(payload.get("model") or self.model_name),
            probability=probability,
            raw_label=label,
            details=details,
            input_chars=len(text),
        )
