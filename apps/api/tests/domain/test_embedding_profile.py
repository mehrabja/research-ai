"""Domain-level embedding profile tests."""
from __future__ import annotations

import pytest

from app.domain.embeddings import (
    EmbeddingBatchResult,
    EmbeddingProfile,
    EmbeddingUsage,
    build_embedding_profile_id,
)


def _profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="openai",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
        profile_version="m9.1",
    )


def test_profile_id_format() -> None:
    pid = build_embedding_profile_id(_profile())
    assert pid == "openai/text-embedding-3-small:1536:cosine:m9.1"


def test_profile_rejects_zero_dimensions() -> None:
    with pytest.raises(ValueError):
        EmbeddingProfile(
            provider="x",
            model="y",
            dimensions=0,
            distance_metric="cosine",
            profile_version="m9.1",
        )


def test_profile_rejects_non_cosine() -> None:
    with pytest.raises(ValueError):
        EmbeddingProfile(
            provider="x",
            model="y",
            dimensions=1536,
            distance_metric="dot",  # type: ignore[arg-type]
            profile_version="m9.1",
        )


def test_usage_rejects_negative_tokens() -> None:
    with pytest.raises(ValueError):
        EmbeddingUsage(input_tokens=-1)


def test_batch_result_basic() -> None:
    result = EmbeddingBatchResult(
        vectors=[[0.1, 0.2], [0.3, 0.4]],
        usage=EmbeddingUsage(input_tokens=42),
        provider_request_id="req-1",
    )
    assert len(result.vectors) == 2
    assert result.usage.input_tokens == 42
