"""Detection domain contracts.

Pure: no SQLAlchemy, FastAPI, HTTP, provider SDKs.
"""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

DetectionLabel = Literal["low", "medium", "high", "unknown"]


@dataclass(frozen=True)
class DetectionProfile:
    provider: str
    model: str
    profile_version: str
    minimum_text_chars: int = 200
    supports_probability: bool = True

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("provider is required")
        if not self.model:
            raise ValueError("model is required")
        if not self.profile_version:
            raise ValueError("profile_version is required")
        if self.minimum_text_chars < 0:
            raise ValueError("minimum_text_chars must be >= 0")


def build_detection_profile_id(profile: DetectionProfile) -> str:
    return f"{profile.provider}/{profile.model}:{profile.profile_version}"


@dataclass(frozen=True)
class DetectionProviderResult:
    provider: str
    model: str
    probability: float | None
    raw_label: str | None
    details: Mapping[str, object] = field(default_factory=dict)
    input_chars: int = 0

    def __post_init__(self) -> None:
        if self.probability is not None and not (
            0.0 <= self.probability <= 1.0
        ):
            raise ValueError("probability must be in [0.0, 1.0]")


@dataclass(frozen=True)
class DetectionResult:
    probability: float | None
    label: DetectionLabel
    provider: str
    model: str
    profile_id: str
    input_hash: str
    input_chars: int


def hash_detection_input(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_detection_identity(
    *,
    report_id: uuid.UUID,
    version_id: uuid.UUID,
    profile_id: str,
    input_hash: str,
) -> str:
    return (
        f"detect:{report_id}:{version_id}:{profile_id}:{input_hash}"
    )


__all__ = [
    "DetectionLabel",
    "DetectionProfile",
    "DetectionProviderResult",
    "DetectionResult",
    "build_detection_identity",
    "build_detection_profile_id",
    "hash_detection_input",
]
