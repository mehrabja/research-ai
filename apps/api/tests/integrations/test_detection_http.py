from types import SimpleNamespace

import httpx
import pytest

import app.integrations.detection.http as detection_http
from app.integrations.detection.base import (
    DetectionAuthenticationError,
    DetectionInputTooLargeError,
    DetectionInvalidResponseError,
    DetectionRateLimitError,
)
from app.integrations.detection.http import HTTPDetectionProvider


def _settings(
    *,
    url: str = "https://detector.example/v1/detect",
    max_retries: int = 2,
    max_chars: int = 100,
) -> SimpleNamespace:
    return SimpleNamespace(
        detection_api_base_url=url,
        detection_api_model="detector-v2",
        ai_detection_api_key="test-key",
        detection_timeout_seconds=5.0,
        detection_max_input_chars=max_chars,
        detection_max_retries=max_retries,
        detection_retry_base_seconds=0.5,
        detection_retry_max_seconds=4.0,
        detection_retry_jitter_fraction=0.0,
    )


def _response(status_code: int, payload: object) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


def test_success_maps_provider_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_post(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return _response(
            200,
            {
                "probability": 0.81,
                "label": "ai_generated",
                "model": "vendor-model",
                "details": {"language": "en", "segments": 3},
            },
        )

    monkeypatch.setattr(detection_http, "get_settings", lambda: _settings())
    monkeypatch.setattr(detection_http.httpx, "post", fake_post)

    result = HTTPDetectionProvider().detect(text="hello world")

    assert result.provider == "http"
    assert result.model == "vendor-model"
    assert result.probability == 0.81
    assert result.raw_label == "ai_generated"
    assert result.input_chars == 11
    assert result.details == {"language": "en", "segments": 3}
    assert calls[0]["kwargs"]["json"] == {"text": "hello world"}
    assert calls[0]["kwargs"]["headers"]["Authorization"] == "Bearer test-key"


def test_rate_limit_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            _response(429, {"error": "rate limited"}),
            _response(200, {"probability": 0.2}),
        ]
    )
    sleeps: list[float] = []

    monkeypatch.setattr(detection_http, "get_settings", lambda: _settings(max_retries=2))
    monkeypatch.setattr(detection_http.httpx, "post", lambda *args, **kwargs: next(responses))

    provider = HTTPDetectionProvider(_sleep=sleeps.append, _random=lambda: 0.0)
    result = provider.detect(text="hello")

    assert result.probability == 0.2
    assert sleeps == [0.5]


def test_authentication_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _response(401, {"error": "unauthorized"})

    monkeypatch.setattr(detection_http, "get_settings", lambda: _settings(max_retries=3))
    monkeypatch.setattr(detection_http.httpx, "post", fake_post)

    with pytest.raises(DetectionAuthenticationError):
        HTTPDetectionProvider().detect(text="hello")

    assert calls == 1


def test_malformed_response_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detection_http, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        detection_http.httpx,
        "post",
        lambda *args, **kwargs: _response(200, {"probability": "not-a-number"}),
    )

    with pytest.raises(DetectionInvalidResponseError):
        HTTPDetectionProvider().detect(text="hello")


def test_input_limit_is_enforced_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        detection_http,
        "get_settings",
        lambda: _settings(max_chars=3),
    )

    with pytest.raises(DetectionInputTooLargeError):
        HTTPDetectionProvider().detect(text="four")


def test_rate_limit_type_is_exposed_for_fallback_policy() -> None:
    assert issubclass(DetectionRateLimitError, Exception)
