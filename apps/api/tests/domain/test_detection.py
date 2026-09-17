"""Domain-level detection contract tests (pure, no DB)."""
from __future__ import annotations

import uuid

import pytest

from app.domain.detection import (
    DetectionProfile,
    DetectionProviderResult,
    build_detection_identity,
    build_detection_profile_id,
    hash_detection_input,
)


def test_profile_id_deterministic() -> None:
    p = DetectionProfile(
        provider="heuristic",
        model="baseline-v1",
        profile_version="m13.1",
    )
    assert (
        build_detection_profile_id(p) == "heuristic/baseline-v1:m13.1"
    )


def test_profile_rejects_bad_minimum() -> None:
    with pytest.raises(ValueError):
        DetectionProfile(
            provider="x",
            model="y",
            profile_version="z",
            minimum_text_chars=-1,
        )


def test_result_rejects_bad_probability() -> None:
    with pytest.raises(ValueError):
        DetectionProviderResult(
            provider="p",
            model="m",
            probability=1.5,
            raw_label=None,
        )


def test_hash_deterministic() -> None:
    assert hash_detection_input("hello") == hash_detection_input(
        "hello"
    )
    assert len(hash_detection_input("hello")) == 64


def test_hash_differs() -> None:
    assert hash_detection_input("a") != hash_detection_input("b")


def test_build_detection_identity_shape() -> None:
    ident = build_detection_identity(
        report_id=uuid.UUID(int=0),
        version_id=uuid.UUID(int=1),
        profile_id="p",
        input_hash="h",
    )
    assert ident.startswith("detect:")
    assert ":p:h" in ident
