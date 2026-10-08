"""Test-only isolation for configuration unit tests.

Settings intentionally read process environment in production. These unit
tests assert defaults, so ambient environment variables must not change the
meaning of a test run.
"""
from __future__ import annotations

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent developer/CI environment from contaminating Settings tests."""
    for field_name in Settings.model_fields:
        monkeypatch.delenv(field_name.upper(), raising=False)
