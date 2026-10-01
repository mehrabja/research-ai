import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_http_detection_provider_requires_endpoint() -> None:
    with pytest.raises(
        ValidationError,
        match="detection_api_base_url is required",
    ):
        Settings(
            _env_file=None,
            database_url="postgresql://example/example",
            detection_provider="http",
            detection_api_base_url="",
        )


def test_originality_detection_provider_requires_production_key() -> None:
    with pytest.raises(
        ValidationError,
        match="AI_DETECTION_API_KEY is required in production",
    ):
        Settings(
            _env_file=None,
            database_url="postgresql://example/example",
            app_env="production",
            detection_provider="originality",
            detection_originality_base_url="https://api.originality.ai/api/v3",
            ai_detection_api_key="",
            jwt_secret_key="x" * 32,
            file_malware_scan_mode="required",
        )


def test_heuristic_detection_provider_is_rejected_in_production() -> None:
    with pytest.raises(
        ValidationError,
        match="detection_provider='heuristic' is not allowed in production",
    ):
        Settings(
            _env_file=None,
            database_url="postgresql://example/example",
            app_env="production",
            detection_provider="heuristic",
            jwt_secret_key="x" * 32,
            file_malware_scan_mode="required",
        )
