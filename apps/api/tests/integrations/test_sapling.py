"""Tests for the Sapling detection adapter."""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.integrations.detection import sapling as module
from app.integrations.detection.base import (
    DetectionAuthenticationError,
    DetectionInvalidResponseError,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: object, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


def _configure(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_PROVIDER", "sapling")
    monkeypatch.setenv("SAPLING_API_KEY", "test-sapling-key")
    get_settings.cache_clear()


def test_sapling_maps_score_to_probability(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(
            200,
            {
                "score": 0.82,
                "sentence_scores": [
                    {"score": 0.9, "sentence": "Example sentence."}
                ],
            },
        ),
    )

    result = module.SaplingDetectionProvider().detect(
        text="x" * 300
    )

    assert result.provider == "sapling"
    assert result.probability == pytest.approx(0.82)
    assert result.details["sentence_scores"]


def test_sapling_rejects_missing_score(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(200, {"text": "x"}),
    )

    with pytest.raises(DetectionInvalidResponseError):
        module.SaplingDetectionProvider().detect(text="x" * 300)


def test_sapling_maps_auth_failure(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(401, {}),
    )

    with pytest.raises(DetectionAuthenticationError):
        module.SaplingDetectionProvider().detect(text="x" * 300)


def test_sapling_requires_key(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_PROVIDER", "sapling")
    monkeypatch.delenv("SAPLING_API_KEY", raising=False)
    get_settings.cache_clear()

    with pytest.raises(DetectionAuthenticationError):
        module.SaplingDetectionProvider().detect(text="x" * 300)
