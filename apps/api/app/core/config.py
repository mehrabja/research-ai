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

    # --- Document extraction (Milestone 8) --------------------------------
    document_fetch_timeout_seconds: float = Field(
        default=20.0, ge=1.0, le=120.0
    )
    document_max_bytes: int = Field(
        default=20 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024
    )
    document_max_redirects: int = Field(default=5, ge=0, le=10)

    # --- Chunking ---------------------------------------------------------
    chunk_target_words: int = Field(default=1200, ge=10, le=10000)
    chunk_overlap_words: int = Field(default=150, ge=0, le=1000)

    # --- Embedding profile (Milestone 9) ----------------------------------
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, ge=1, le=4096)
    embedding_distance_metric: str = "cosine"
    embedding_profile_version: str = "m9.1"

    # --- Embedding runtime ------------------------------------------------
    embedding_openai_api_key: str = Field(default="", repr=False)
    embedding_openai_base_url: str = "https://api.openai.com/v1"
    embedding_batch_size: int = Field(default=64, ge=1, le=512)
    embedding_timeout_seconds: float = Field(
        default=30.0, ge=1.0, le=300.0
    )
    embedding_max_retries: int = Field(default=3, ge=0, le=10)
    embedding_retry_base_seconds: float = Field(
        default=1.0, ge=0.1, le=30.0
    )
    embedding_retry_max_seconds: float = Field(
        default=10.0, ge=0.1, le=120.0
    )
    embedding_retry_jitter_fraction: float = Field(
        default=0.25, ge=0.0, le=1.0
    )
    embedding_processing_timeout_seconds: int = Field(
        default=120, ge=10, le=3600
    )

    # --- Retrieval --------------------------------------------------------
    embedding_retrieval_candidate_multiplier: int = Field(
        default=4, ge=1, le=20
    )
    embedding_retrieval_top_k_default: int = Field(
        default=8, ge=1, le=100
    )
    embedding_retrieval_top_k_max: int = Field(
        default=50, ge=1, le=200
    )
    embedding_rrf_k: int = Field(default=60, ge=1, le=1000)
    embedding_vector_weight: float = Field(
        default=1.0, ge=0.0, le=10.0
    )
    embedding_lexical_weight: float = Field(
        default=1.0, ge=0.0, le=10.0
    )

    # --- HNSW filtered ANN ------------------------------------------------
    embedding_hnsw_ef_search: int = Field(default=100, ge=1, le=4000)
    embedding_hnsw_iterative_scan: Literal[
        "off", "strict_order", "relaxed_order"
    ] = "strict_order"
    embedding_hnsw_max_scan_tuples: int = Field(
        default=20_000, ge=100, le=1_000_000
    )
    embedding_hnsw_scan_mem_multiplier: float = Field(
        default=1.0, ge=0.1, le=10.0
    )

    # --- Job Queue / Worker (Milestone 10) --------------------------------
    job_default_max_attempts: int = Field(default=3, ge=1, le=20)
    job_retry_base_seconds: float = Field(
        default=1.0, ge=0.1, le=60.0
    )
    job_retry_max_seconds: float = Field(
        default=300.0, ge=1.0, le=3600.0
    )
    job_retry_jitter: float = Field(default=0.25, ge=0.0, le=1.0)
    job_processing_timeout_seconds: int = Field(
        default=300, ge=30, le=86400
    )
    job_heartbeat_interval_seconds: int = Field(
        default=30, ge=5, le=3600
    )
    job_poll_interval_seconds: float = Field(
        default=1.0, ge=0.1, le=60.0
    )
    job_payload_max_bytes: int = Field(
        default=65536, ge=256, le=10 * 1024 * 1024
    )
    @model_validator(mode="after")
    def _validate_production_secrets(self) -> Settings:
        if self.app_env.lower() == "production":
            if self.jwt_secret_key == DEV_JWT_SECRET:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a non-default value "
                    "when APP_ENV=production."
                )

            if (
                len(self.jwt_secret_key.encode("utf-8"))
                < _MIN_JWT_SECRET_BYTES
            ):
                raise ValueError(
                    f"JWT_SECRET_KEY must be at least "
                    f"{_MIN_JWT_SECRET_BYTES} bytes when "
                    "APP_ENV=production."
                )
        return self

    @model_validator(mode="after")
    def _validate_chunk_config(self) -> Settings:
        if self.chunk_overlap_words >= self.chunk_target_words:
            raise ValueError(
                "chunk_overlap_words must be strictly less than "
                "chunk_target_words"
            )
        return self

    @model_validator(mode="after")
    def _validate_embedding_config(self) -> Settings:
        if self.embedding_distance_metric != "cosine":
            raise ValueError("only cosine is supported")
        if (
            self.embedding_vector_weight
            + self.embedding_lexical_weight
            <= 0
        ):
            raise ValueError("sum of weights must be > 0")
        if (
            self.embedding_retrieval_top_k_max
            < self.embedding_retrieval_top_k_default
        ):
            raise ValueError(
                "top_k_max must be >= top_k_default"
            )
        if (
            self.embedding_retry_max_seconds
            < self.embedding_retry_base_seconds
        ):
            raise ValueError(
                "retry_max must be >= retry_base"
            )
        if self.embedding_hnsw_iterative_scan not in (
            "off", "strict_order", "relaxed_order"
        ):
            raise ValueError(
                "hnsw_iterative_scan must be "
                "off/strict_order/relaxed_order"
            )
        return self
    @model_validator(mode="after")
    def _validate_job_config(self) -> Settings:
        if self.job_retry_max_seconds < self.job_retry_base_seconds:
            raise ValueError(
                "job_retry_max_seconds must be >= "
                "job_retry_base_seconds"
            )
        if (
            self.job_heartbeat_interval_seconds
            >= self.job_processing_timeout_seconds
        ):
            raise ValueError(
                "job_heartbeat_interval_seconds must be < "
                "job_processing_timeout_seconds"
            )
        return self

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
