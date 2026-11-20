"""Shared constructor for the current detection profile + provider."""
from __future__ import annotations

from app.core.config import get_settings
from app.domain.detection import (
    DetectionProfile,
    build_detection_profile_id,
)
from app.integrations.detection.base import DetectionProvider
from app.providers.registry import ProviderCapability, ProviderContext, resolve_provider


def get_current_detection_profile() -> DetectionProfile:
    s = get_settings()
    provider = s.detection_provider.strip().lower()
    if provider == "http" and s.detection_api_model.strip():
        model = s.detection_api_model
    elif provider == "originality" and s.detection_originality_model.strip():
        model = s.detection_originality_model
    elif provider == "sapling" and s.detection_sapling_model.strip():
        model = s.detection_sapling_model
    else:
        model = s.detection_model
    return DetectionProfile(
        provider=provider,
        model=model,
        profile_version=s.detection_profile_version,
        minimum_text_chars=s.detection_minimum_text_chars,
        supports_probability=True,
    )


def get_current_detection_profile_id() -> str:
    return build_detection_profile_id(get_current_detection_profile())


def build_detection_provider(
    profile: DetectionProfile | None = None,
) -> DetectionProvider:
    p = profile or get_current_detection_profile()
    return resolve_provider(
        capability=ProviderCapability.DETECTION,
        preferred=p.provider,
        context=ProviderContext(profile=p),
    )


__all__ = [
    "build_detection_provider",
    "get_current_detection_profile",
    "get_current_detection_profile_id",
]
