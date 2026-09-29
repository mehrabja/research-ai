from pydantic import ValidationError
import pytest

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
