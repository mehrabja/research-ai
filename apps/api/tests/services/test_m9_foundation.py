"""Smoke tests for M9 config + exception wiring."""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.exceptions import (
    EmbeddingConfigurationError,
    EmbeddingInvalidResponseAppError,
    EmbeddingProviderUnavailableAppError,
    EmbeddingRateLimitAppError,
    EmbeddingsNotReadyError,
    RetrievalConfigurationError,
    SourceNotReadyForEmbedding,
)


def test_embedding_defaults_are_coherent() -> None:
    s = get_settings()
    assert s.embedding_provider == "openai"
    assert s.embedding_model == "text-embedding-3-small"
    assert s.embedding_dimensions == 1536
    assert s.embedding_distance_metric == "cosine"
    assert 1 <= s.embedding_batch_size <= 512
    assert s.embedding_retry_max_seconds >= (
        s.embedding_retry_base_seconds
    )
    assert s.embedding_retrieval_top_k_max >= (
        s.embedding_retrieval_top_k_default
    )
    assert (
        s.embedding_vector_weight + s.embedding_lexical_weight
    ) > 0
    assert s.embedding_hnsw_iterative_scan in (
        "off", "strict_order", "relaxed_order"
    )


def test_embedding_config_rejects_bad_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import ValidationError

    from app.core import config as cfg

    monkeypatch.setenv("EMBEDDING_VECTOR_WEIGHT", "0")
    monkeypatch.setenv("EMBEDDING_LEXICAL_WEIGHT", "0")
    cfg.get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError):
            cfg.Settings()
    finally:
        cfg.get_settings.cache_clear()


def test_embedding_exception_codes() -> None:
    cases = [
        (EmbeddingConfigurationError, "EMBEDDING_CONFIGURATION_ERROR", 500),
        (
            EmbeddingProviderUnavailableAppError,
            "EMBEDDING_PROVIDER_UNAVAILABLE",
            502,
        ),
        (EmbeddingRateLimitAppError, "EMBEDDING_RATE_LIMITED", 429),
        (
            EmbeddingInvalidResponseAppError,
            "EMBEDDING_INVALID_RESPONSE",
            502,
        ),
        (EmbeddingsNotReadyError, "EMBEDDINGS_NOT_READY", 409),
        (
            RetrievalConfigurationError,
            "RETRIEVAL_CONFIGURATION_ERROR",
            422,
        ),
        (
            SourceNotReadyForEmbedding,
            "SOURCE_NOT_READY_FOR_EMBEDDING",
            409,
        ),
    ]
    for cls, code, status in cases:
        assert cls.code == code
        assert cls.status_code == status
