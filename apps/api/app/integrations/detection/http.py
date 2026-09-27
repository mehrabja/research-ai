from __future__ import annotations

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


class HTTPDetectionProvider:
    """Provider-neutral HTTP detector adapter.

    The endpoint accepts JSON {"text": "..."} and returns an object with
    "probability" plus optional "label" and "details".
    """

    provider_name = "http"

    def __init__(self) -> None:
        settings = get_settings()
        self._url = settings.detection_api_base_url.rstrip("/")
        self.model_name = settings.detection_api_model
        self._key = settings.ai_detection_api_key
        self._timeout = settings.detection_timeout_seconds
        self._max_chars = settings.detection_max_input_chars

    def detect(self, *, text: str) -> DetectionProviderResult:
        if not self._url:
            raise DetectionProviderUnavailableError("detection endpoint is not configured")
        if len(text) > self._max_chars:
            raise DetectionInputTooLargeError("text exceeds detector input limit")

        headers = {"Content-Type": "application/json"}
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
            raise DetectionProviderUnavailableError("detector transport failed") from exc

        if response.status_code in (401, 403):
            raise DetectionAuthenticationError("detector authentication failed")
        if response.status_code == 429:
            raise DetectionRateLimitError("detector rate limited request")
        if 500 <= response.status_code < 600:
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
            raise DetectionInvalidResponseError("detector returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise DetectionInvalidResponseError("detector response must be an object")

        probability = payload.get("probability")
        if probability is not None:
            try:
                probability = float(probability)
            except (TypeError, ValueError) as exc:
                raise DetectionInvalidResponseError("probability is not numeric") from exc
            if not 0.0 <= probability <= 1.0:
                raise DetectionInvalidResponseError("probability must be between 0 and 1")

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
