"""Central, type-safe configuration."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT: Path = Path(__file__).resolve().parents[4]

DEV_JWT_SECRET: str = "dev-insecure-secret-change-me-before-production"
_MIN_JWT_SECRET_BYTES: int = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    debug: bool = False
    project_name: str = "research-ai"
    api_prefix: str = "/api/v1"

    database_url: str = Field(..., repr=False)

    # JWT
    jwt_secret_key: str = Field(default=DEV_JWT_SECRET, repr=False)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1)
    jwt_issuer: str = "research-ai"
    jwt_audience: str = "research-ai-api"
    jwt_type: str = "access+jwt"
    jwt_clock_skew_seconds: int = Field(default=30, ge=0)

    # Login throttling
    login_rate_limit: int = Field(default=5, ge=1)
    login_rate_window_seconds: int = Field(default=300, ge=1)

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> Settings:
        if self.app_env.lower() == "production":
            if self.jwt_secret_key == DEV_JWT_SECRET:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a non-default value "
                    "when APP_ENV=production."
                )

            if len(self.jwt_secret_key.encode("utf-8")) < _MIN_JWT_SECRET_BYTES:
                raise ValueError(
                    f"JWT_SECRET_KEY must be at least {_MIN_JWT_SECRET_BYTES} "
                    "bytes when APP_ENV=production."
                )

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
