"""Domain-owned embedding contracts.

No framework, provider, or infrastructure imports. Token counting is
provider-specific and lives outside this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EmbeddingDistanceMetric = Literal["cosine"]


@dataclass(frozen=True)
class EmbeddingProfile:
    provider: str
    model: str
    dimensions: int
    distance_metric: EmbeddingDistanceMetric
    profile_version: str

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("provider is required")
        if not self.model:
            raise ValueError("model is required")
        if self.dimensions <= 0:
            raise ValueError("dimensions must be positive")
        if self.distance_metric != "cosine":
            raise ValueError(
                f"unsupported distance metric: {self.distance_metric!r}"
            )
        if not self.profile_version:
            raise ValueError("profile_version is required")


@dataclass(frozen=True)
class EmbeddingUsage:
    input_tokens: int
    request_count: int = 1

    def __post_init__(self) -> None:
        if self.input_tokens < 0:
            raise ValueError("input_tokens must be >= 0")
        if self.request_count < 0:
            raise ValueError("request_count must be >= 0")


@dataclass(frozen=True)
class EmbeddingBatchResult:
    vectors: list[list[float]]
    usage: EmbeddingUsage
    provider_request_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


def build_embedding_profile_id(profile: EmbeddingProfile) -> str:
    """Deterministic: ``{provider}/{model}:{dims}:{metric}:{version}``."""
    return (
        f"{profile.provider}/{profile.model}:"
        f"{profile.dimensions}:{profile.distance_metric}:"
        f"{profile.profile_version}"
    )


__all__ = [
    "EmbeddingBatchResult",
    "EmbeddingDistanceMetric",
    "EmbeddingProfile",
    "EmbeddingUsage",
    "build_embedding_profile_id",
]
