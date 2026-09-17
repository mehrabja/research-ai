from __future__ import annotations

import uuid

import pytest

from app.domain.generation import (
    EmptyGenerationError,
    EvidenceItem,
    EvidenceSet,
    GenerationProfile,
    UnknownEvidenceMarkerError,
    build_generation_profile_id,
    extract_citation_markers,
    validate_generation_output,
)


def _profile() -> GenerationProfile:
    return GenerationProfile(
        provider="openai", model="gpt-4o-mini",
        temperature=0.2, max_output_tokens=2000,
        profile_version="m12.1",
    )


def test_profile_id_is_deterministic() -> None:
    p = _profile()
    assert build_generation_profile_id(p) == build_generation_profile_id(p)


def test_profile_rejects_bad_temperature() -> None:
    with pytest.raises(ValueError):
        GenerationProfile(
            provider="x", model="y", temperature=3.0,
            max_output_tokens=100, profile_version="v",
        )


def test_extract_markers_order_and_dedup() -> None:
    text = "A [E1] B [E2] C [E1]"
    assert extract_citation_markers(text) == ("[E1]", "[E2]")


def _evidence() -> EvidenceSet:
    sid = uuid.uuid4()
    cid = uuid.uuid4()
    return EvidenceSet(items=(
        EvidenceItem(
            rank=1, marker="[E1]",
            evidence_id=f"source:{sid}:chunk:{cid}",
            source_id=sid, chunk_id=cid,
            content="x", fusion_score=0.5,
        ),
    ))


def test_validate_empty_text_rejected() -> None:
    with pytest.raises(EmptyGenerationError):
        validate_generation_output(text="   ", evidence=_evidence())


def test_validate_unknown_marker_rejected() -> None:
    with pytest.raises(UnknownEvidenceMarkerError):
        validate_generation_output(
            text="claim [E99]", evidence=_evidence()
        )


def test_validate_success() -> None:
    cited = validate_generation_output(
        text="claim [E1]", evidence=_evidence()
    )
    assert cited == ("[E1]",)
