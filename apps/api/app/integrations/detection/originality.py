"""Originality.ai V3 AI-text detection adapter."""
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


class OriginalityDetectionProvider:
    """Provider adapter for Originality.ai's Version 3 text scan API."""

    provider_name = "originality"

    def __init__(
        self,
        *,
        _sleep: Callable[[float], None] = time.sleep,
        _random: Callable[[], float] = random.random,
    ) -> None:
        settings = get_settings()
        self._base_url = settings.detection_originality_base_url.rstrip("/")
        self.model_name = settings.detection_originality_model
        self._key = settings.ai_detection_api_key
        self._timeout = float(settings.detection_timeout_seconds)
        self._max_chars = int(settings.detection_max_input_chars)
        self._max_retries = int(settings.detection_max_retries)
        self._retry_base = float(settings.detection_retry_base_seconds)
        self._retry_max = float(settings.detection_retry_max_seconds)
        self._jitter = float(settings.detection_retry_jitter_fraction)
        self._store_scan = bool(settings.detection_originality_store_scan)
        self._sleep = _sleep
        self._random = _random

    def detect(self, *, text: str) -> DetectionProviderResult:
        if not self._base_url:
            raise DetectionProviderUnavailableError(
                "Originality.ai detection endpoint is not configured"
            )
        if not self._key:
            raise DetectionAuthenticationError(
                "Originality.ai API key is not configured"
            )
        if len(text) > self._max_chars:
            raise DetectionInputTooLargeError(
                "text exceeds the configured Originality.ai input limit"
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
                    retry_after=exc.retry_after
                    if isinstance(exc, DetectionRateLimitError)
                    else None,
                )
                self._sleep(delay)
                logger.warning(
                    "originality_detection_retry attempt=%d provider=%s",
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
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-OAI-API-KEY": self._key,
        }
        payload = {
            "title": "research-ai detection",
            "check_ai": True,
            "check_plagiarism": False,
            "check_facts": False,
            "check_readability": False,
            "check_grammar": False,
            "storeScan": self._store_scan,
            "aiModelVersion": self.model_name,
            "content": text,
        }

        try:
            response = httpx.post(
                self._base_url + "/scan",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise DetectionTimeoutError(
                "Originality.ai request timed out"
            ) from exc
        except httpx.HTTPError as exc:
            raise DetectionProviderUnavailableError(
                "Originality.ai transport failed"
            ) from exc

        if response.status_code in (401, 403):
            raise DetectionAuthenticationError(
                f"Originality.ai authentication failed: HTTP {response.status_code}"
            )
        if response.status_code == 402:
            raise DetectionQuotaExceededError(
                "Originality.ai account has insufficient credits"
            )
        if response.status_code == 413:
            raise DetectionInputTooLargeError(
                "Originality.ai rejected the request as too large"
            )
        if response.status_code in _RETRYABLE_STATUSES:
            if response.status_code == 429:
                raise DetectionRateLimitError(
                    f"Originality.ai rate limited request: HTTP {response.status_code}",
                    retry_after=_parse_retry_after(
                        response.headers.get("Retry-After")
                    ),
                )
            raise DetectionProviderUnavailableError(
                f"Originality.ai server error: HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            raise DetectionInvalidRequestError(
                f"Originality.ai rejected request: HTTP {response.status_code}"
            )

        try:
            raw: Any = response.json()
        except ValueError as exc:
            raise DetectionInvalidResponseError(
                "Originality.ai returned invalid JSON"
            ) from exc
        if not isinstance(raw, dict):
            raise DetectionInvalidResponseError(
                "Originality.ai response must be an object"
            )

        return _normalize_response(
            raw,
            input_chars=len(text),
            configured_model=self.model_name,
        )


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _as_probability(value: object, *, field_name: str) -> float:
    try:
        probability = float(value)
    except (TypeError, ValueError) as exc:
        raise DetectionInvalidResponseError(
            f"Originality.ai field {field_name!r} is not numeric"
        ) from exc
    if not 0.0 <= probability <= 1.0:
        raise DetectionInvalidResponseError(
            f"Originality.ai field {field_name!r} must be between 0 and 1"
        )
    return probability


def _normalize_response(
    payload: dict[str, Any],
    *,
    input_chars: int,
    configured_model: str,
) -> DetectionProviderResult:
    results = payload.get("results")
    if not isinstance(results, dict):
        raise DetectionInvalidResponseError(
            "Originality.ai response is missing results"
        )

    ai = results.get("ai")
    if not isinstance(ai, dict):
        raise DetectionInvalidResponseError(
            "Originality.ai response is missing results.ai"
        )

    confidence = ai.get("confidence")
    if not isinstance(confidence, dict) or "AI" not in confidence:
        raise DetectionInvalidResponseError(
            "Originality.ai response is missing results.ai.confidence.AI"
        )

    probability = _as_probability(
        confidence["AI"],
        field_name="results.ai.confidence.AI",
    )

    classification = ai.get("classification")
    raw_label: str | None = None
    if isinstance(classification, dict):
        ai_score = classification.get("AI")
        original_score = classification.get("Original")
        mixed_score = classification.get("Mixed")
        if isinstance(ai_score, (int, float)) and ai_score > 0:
            raw_label = "AI"
        elif isinstance(mixed_score, (int, float)) and mixed_score > 0:
            raw_label = "Mixed"
        elif isinstance(original_score, (int, float)) and original_score > 0:
            raw_label = "Original"

    model = str(ai.get("aiModel") or configured_model)

    confidence_original = confidence.get("Original")
    original_probability = (
        _as_probability(
            confidence_original,
            field_name="results.ai.confidence.Original",
        )
        if confidence_original is not None
        else None
    )

    block_details: list[dict[str, object]] = []
    blocks = ai.get("blocks")
    if isinstance(blocks, list):
        for item in blocks:
            if not isinstance(item, dict):
                continue
            result = item.get("result")
            if not isinstance(result, dict):
                continue
            detail: dict[str, object] = {"status": result.get("status")}
            if result.get("fake") is not None:
                detail["fake"] = _as_probability(
                    result["fake"],
                    field_name="results.ai.blocks[].result.fake",
                )
            if result.get("real") is not None:
                detail["real"] = _as_probability(
                    result["real"],
                    field_name="results.ai.blocks[].result.real",
                )
            block_details.append(detail)

    credits_used: int | float | None = None
    credits = results.get("credits")
    if isinstance(credits, dict) and credits.get("used") is not None:
        try:
            credits_used = float(credits["used"])
        except (TypeError, ValueError) as exc:
            raise DetectionInvalidResponseError(
                "Originality.ai credits.used is not numeric"
            ) from exc

    scan_id = (
        payload.get("scanID")
        or payload.get("scanId")
        or (
            results.get("properties", {}).get("id")
            if isinstance(results.get("properties"), dict)
            else None
        )
    )

    details: dict[str, object] = {
        "classification": classification if isinstance(classification, dict) else {},
        "confidence_original": original_probability,
        "credits_used": credits_used,
        "blocks": block_details,
    }
    if scan_id is not None:
        details["scan_id"] = str(scan_id)

    return DetectionProviderResult(
        provider="originality",
        model=model,
        probability=probability,
        raw_label=raw_label,
        details=details,
        input_chars=input_chars,
    )


__all__ = ["OriginalityDetectionProvider"]
