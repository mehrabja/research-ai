from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import detection_profile


def _settings(*, provider: str, detection_model: str, api_model: str) -> SimpleNamespace:
    return SimpleNamespace(
        detection_provider=provider,
        detection_model=detection_model,
        detection_api_model=api_model,
        detection_profile_version="m13.1",
        detection_minimum_text_chars=200,
    )


@pytest.mark.parametrize(
    ("provider", "expected_model"),
    [
        ("http", "vendor-detector-v2"),
        ("heuristic", "baseline-v1"),
    ],
)
def test_current_detection_profile_uses_active_provider_model(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    expected_model: str,
) -> None:
    monkeypatch.setattr(
        detection_profile,
        "get_settings",
        lambda: _settings(
            provider=provider,
            detection_model="baseline-v1",
            api_model="vendor-detector-v2",
        ),
    )

    profile = detection_profile.get_current_detection_profile()

    assert profile.provider == provider
    assert profile.model == expected_model
