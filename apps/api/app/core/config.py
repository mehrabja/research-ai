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

    # --- Generation (Milestone 12) ----------------------------------------
    generation_provider: str = "openai"
    generation_model: str = "gpt-4o-mini"
    generation_temperature: float = Field(
        default=0.2, ge=0.0, le=2.0
    )
    generation_max_output_tokens: int = Field(
        default=2000, ge=64, le=32000
    )
    generation_max_context_chunks: int = Field(
        default=8, ge=1, le=50
    )
    generation_profile_version: str = "m12.1"
    generation_openai_api_key: str = Field(default="", repr=False)
    generation_openai_base_url: str = "https://api.openai.com/v1"
    generation_timeout_seconds: float = Field(
        default=60.0, ge=5.0, le=600.0
    )
    generation_max_retries: int = Field(default=2, ge=0, le=10)
    generation_retry_base_seconds: float = Field(
        default=1.0, ge=0.1, le=60.0
    )
    generation_retry_max_seconds: float = Field(
        default=30.0, ge=1.0, le=600.0
    )
    generation_retry_jitter_fraction: float = Field(
        default=0.25, ge=0.0, le=1.0
    )

    # --- Detection (Milestone 13) -----------------------------------------
    detection_provider: str = "heuristic"
    detection_model: str = "baseline-v1"
    detection_profile_version: str = "m13.1"
    detection_minimum_text_chars: int = Field(
        default=200, ge=0, le=10000
    )

    # --- Humanization (Milestone 14) --------------------------------------
    humanization_enabled: bool = True
    humanization_policy_version: str = "m14.1"
    humanization_temperature: float = Field(
        default=0.4, ge=0.0, le=2.0
    )
    humanization_max_output_tokens: int = Field(
        default=2048, ge=64, le=32000
    )
    humanization_max_segments: int = Field(
        default=50, ge=1, le=500
    )
    humanization_max_total_tokens: int = Field(
        default=60_000, ge=100, le=1_000_000
    )
    humanization_max_segment_chars: int = Field(
        default=4_000, ge=50, le=100_000
    )
    humanization_allow_partial: bool = False
    humanization_max_preservation_retries: int = Field(
        default=1, ge=0, le=5
    )
    # --- Translation (Milestone 16) ---------------------------------------
    translation_enabled: bool = True
    translation_provider: str = "openai"
    translation_model: str = "gpt-4o-mini"
    translation_temperature: float = Field(
        default=0.1, ge=0.0, le=2.0
    )
    translation_max_output_tokens: int = Field(
        default=8000, ge=64, le=16000
    )
    translation_profile_version: str = "m16.1"
    translation_timeout_seconds: float = Field(
        default=90.0, ge=5.0, le=600.0
    )
    translation_max_retries: int = Field(default=2, ge=0, le=10)
    translation_retry_base_seconds: float = Field(
        default=1.0, ge=0.1, le=60.0
    )
    translation_retry_max_seconds: float = Field(
        default=30.0, ge=1.0, le=600.0
    )
    translation_retry_jitter_fraction: float = Field(
        default=0.25, ge=0.0, le=1.0
    )
    translation_max_input_chars: int = Field(
        default=12_000, ge=100, le=1_000_000
    )
    translation_max_output_chars: int = Field(
        default=40_000, ge=100, le=2_000_000
    )
    translation_preservation_retry_count: int = Field(
        default=1, ge=0, le=3
    )
    # --- Post-Translation Humanization (Milestone 17) ---------------------
    post_translation_humanization_enabled: bool = True
    post_translation_humanization_policy_version: str = "m17.1"
    post_translation_humanization_temperature: float = Field(
        default=0.4, ge=0.0, le=2.0
    )
    post_translation_humanization_max_output_tokens: int = Field(
        default=2048, ge=64, le=32000
    )
    post_translation_humanization_max_segments: int = Field(
        default=50, ge=1, le=500
    )
    post_translation_humanization_max_total_tokens: int = Field(
        default=60_000, ge=100, le=1_000_000
    )
    post_translation_humanization_max_segment_chars: int = Field(
        default=4_000, ge=50, le=100_000
    )
    post_translation_humanization_max_preservation_retries: int = Field(
        default=1, ge=0, le=5
    )
    # Lease expiry is DERIVED from provider execution limits. These are
    # added on top of the derived maximum active provider window:
    #   max_active = timeout × (retries + 1)
    #              + retry_max_seconds × (retries + 1)
    #   lease_expires_at = now() + max_active + safety_margin_seconds
    post_translation_humanization_lease_safety_margin_seconds: int = Field(
        default=120, ge=30, le=3600
    )
    post_translation_detection_lease_safety_margin_seconds: int = Field(
        default=60, ge=30, le=3600
    )

    # --- Semantic Scholar / Source Discovery (M7) -------------------------
    semantic_scholar_api_key: str = Field(default="", repr=False)
    semantic_scholar_base_url: str = (
        "https://api.semanticscholar.org/graph/v1"
    )
    semantic_scholar_timeout_seconds: float = Field(
        default=15.0, ge=1.0, le=120.0
    )
    semantic_scholar_max_retries: int = Field(default=3, ge=0, le=10)
    source_search_limit_default: int = Field(default=10, ge=1, le=100)
    source_search_limit_max: int = Field(default=50, ge=1, le=100)

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

    @model_validator(mode="after")
    def _validate_generation_config(self) -> Settings:
        if (
            self.generation_retry_max_seconds
            < self.generation_retry_base_seconds
        ):
            raise ValueError(
                "generation_retry_max_seconds must be >= base"
            )
        return self

    @model_validator(mode="after")
    def _validate_detection_config(self) -> Settings:
        if self.detection_minimum_text_chars < 0:
            raise ValueError(
                "detection_minimum_text_chars must be >= 0"
            )
        return self

    @model_validator(mode="after")
    def _validate_source_discovery_config(self) -> Settings:
        if self.source_search_limit_max < self.source_search_limit_default:
            raise ValueError(
                "source_search_limit_max must be >= "
                "source_search_limit_default"
            )
        if not self.semantic_scholar_base_url.startswith(
            ("http://", "https://")
        ):
            raise ValueError(
                "semantic_scholar_base_url must start with http(s)://"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
