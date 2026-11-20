from types import SimpleNamespace

import httpx
import pytest

import app.integrations.detection.originality as originality
from app.integrations.detection.base import (
    DetectionAuthenticationError,
    DetectionInputTooLargeError,
    DetectionInvalidResponseError,
    DetectionQuotaExceededError,
)
from app.integrations.detection.originality import OriginalityDetectionProvider


def _settings(
    *,
    retries: int = 2,
    max_chars: int = 100,
    model: str = "multilang",
) -> SimpleNamespace:
    return SimpleNamespace(
        detection_originality_base_url="https://api.originality.ai/api/v3",
        detection_originality_model=model,
        detection_originality_store_scan=False,
        ai_detection_api_key="test-key",
        detection_timeout_seconds=5.0,
        detection_max_input_chars=max_chars,
        detection_max_retries=retries,
        detection_retry_base_seconds=0.5,
        detection_retry_max_seconds=4.0,
        detection_retry_jitter_fraction=0.0,
    )


def _response(
    status_code: int,
    payload: object,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(status_code, json=payload, headers=headers)


def _payload() -> dict[str, object]:
    return {
        "scanID": "scan-123",
        "results": {
            "credits": {"used": 7},
            "ai": {
                "aiModel": "multilang",
                "classification": {"AI": 1, "Original": 0},
                "confidence": {"AI": 0.87, "Original": 0.13},
                "blocks": [
                    {
                        "text": "must not persist",
                        "result": {
                            "fake": 0.91,
                            "real": 0.09,
                            "status": "success",
                        },
                    }
                ],
            },
        },
    }


def test_success_normalizes_originality_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(originality, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        originality.httpx,
        "post",
        lambda *args, **kwargs: calls.append(
            {"args": args, "kwargs": kwargs}
        )
        or _response(200, _payload()),
    )

    result = OriginalityDetectionProvider().detect(text="hello world")

    assert result.provider == "originality"
    assert result.model == "multilang"
    assert result.probability == 0.87
    assert result.raw_label == "AI"
    assert result.input_chars == 11
    assert result.details["scan_id"] == "scan-123"
    assert result.details["credits_used"] == 7.0
    assert result.details["blocks"] == [
        {"status": "success", "fake": 0.91, "real": 0.09}
    ]

    request = calls[0]["kwargs"]
    assert request["headers"]["X-OAI-API-KEY"] == "test-key"
    assert request["json"]["aiModelVersion"] == "multilang"
    assert request["json"]["check_ai"] is True
    assert request["json"]["storeScan"] is False
    assert request["json"]["content"] == "hello world"
    assert request["json"]["check_plagiarism"] is False


def test_rate_limit_uses_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            _response(
                429,
                {"error": "rate"},
                headers={"Retry-After": "3"},
            ),
            _response(200, _payload()),
        ]
    )
    sleeps: list[float] = []
    monkeypatch.setattr(originality, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        originality.httpx,
        "post",
        lambda *args, **kwargs: next(responses),
    )

    result = OriginalityDetectionProvider(
        _sleep=sleeps.append,
        _random=lambda: 0.0,
    ).detect(text="hello")

    assert result.probability == 0.87
    assert sleeps == [3.0]


def test_authentication_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _response(401, {"error": "unauthorized"})

    monkeypatch.setattr(
        originality,
        "get_settings",
        lambda: _settings(retries=3),
    )
    monkeypatch.setattr(originality.httpx, "post", fake_post)

    with pytest.raises(DetectionAuthenticationError):
        OriginalityDetectionProvider().detect(text="hello")

    assert calls == 1


def test_quota_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _response(402, {"error": "insufficient credits"})

    monkeypatch.setattr(
        originality,
        "get_settings",
        lambda: _settings(retries=3),
    )
    monkeypatch.setattr(originality.httpx, "post", fake_post)

    with pytest.raises(DetectionQuotaExceededError):
        OriginalityDetectionProvider().detect(text="hello")

    assert calls == 1


def test_malformed_response_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(originality, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        originality.httpx,
        "post",
        lambda *args, **kwargs: _response(
            200,
            {"results": {"ai": {"confidence": {"AI": "bad"}}}},
        ),
    )

    with pytest.raises(DetectionInvalidResponseError):
        OriginalityDetectionProvider().detect(text="hello")


def test_input_limit_is_enforced_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        originality,
        "get_settings",
        lambda: _settings(max_chars=3),
    )

    with pytest.raises(DetectionInputTooLargeError):
        OriginalityDetectionProvider().detect(text="four")
