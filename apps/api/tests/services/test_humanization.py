"""M14 — service-level tests that don't require DB fixtures."""

from __future__ import annotations

import pytest

from app.domain.humanization import (
    HumanizationBudgetExceededError,
    HumanizationLayer,
    HumanizationPolicy,
    HumanizationPreservationError,
    HumanizationSegmentTooLargeError,
    HumanizationStage,
    default_pre_translation_policy,
)

# ---------------------------------------------------------------------------
# Pure-domain checks that don't touch DB
# ---------------------------------------------------------------------------

def test_default_policy_shape():
    p = default_pre_translation_policy(job_id="j1")
    assert p.job_id == "j1"
    assert p.stage == HumanizationStage.PRE_TRANSLATION
    assert p.enabled_layers == (
        HumanizationLayer.L1,
        HumanizationLayer.L2,
        HumanizationLayer.L3,
    )


def test_policy_roundtrip():
    p = default_pre_translation_policy(job_id="j1")
    assert HumanizationPolicy.from_mapping(p.to_jsonable()) == p


def test_policy_rejects_oversize_threshold():
    with pytest.raises(Exception):
        HumanizationPolicy(
            version="m14.1",
            stage=HumanizationStage.PRE_TRANSLATION,
            enabled_layers=(HumanizationLayer.L1,),
            max_segments=1,
            max_total_tokens=1,
            max_segment_chars=0,  # invalid
            allow_partial=False,
            temperature=0.4,
            max_output_tokens=1,
            max_preservation_retries=0,
        )


# ---------------------------------------------------------------------------
# Error class existence checks
# ---------------------------------------------------------------------------

def test_error_classes_exist():
    assert issubclass(HumanizationBudgetExceededError, Exception)
    assert issubclass(HumanizationPreservationError, Exception)
    assert issubclass(HumanizationSegmentTooLargeError, Exception)


# ---------------------------------------------------------------------------
# Idempotency key helpers
# ---------------------------------------------------------------------------

def test_idempotency_keys_are_stable():
    from app.domain.humanization import (
        build_humanization_job_idempotency_key,
        build_rewrite_idempotency_key,
    )

    k1 = build_humanization_job_idempotency_key(
        report_id="r", version_id="v",
        detection_run_id="d", policy_version="m14.1",
    )
    k2 = build_humanization_job_idempotency_key(
        report_id="r", version_id="v",
        detection_run_id="d", policy_version="m14.1",
    )
    assert k1 == k2

    rk = build_rewrite_idempotency_key(
        job_id="j", version_id="v", segment_id="s",
        layer="L1", policy_version="m14.1",
    )
    assert rk == "humanize:j:v:s:L1:m14.1"


# ---------------------------------------------------------------------------
# Preservation validator smoke checks
# ---------------------------------------------------------------------------

def test_preservation_detects_marker_loss():
    from app.domain.humanization_preservation import (
        extract_protected_tokens,
        validate_preservation,
    )

    before = extract_protected_tokens("Result [E1] and [E2].")
    after = extract_protected_tokens("Result [E1].")
    assert not validate_preservation(before, after).ok


def test_preservation_detects_marker_invention():
    from app.domain.humanization_preservation import (
        extract_protected_tokens,
        validate_preservation,
    )

    before = extract_protected_tokens("Result [E1].")
    after = extract_protected_tokens("Result [E1] [E99].")
    assert not validate_preservation(before, after).ok


def test_preservation_detects_number_mutation():
    from app.domain.humanization_preservation import (
        extract_protected_tokens,
        validate_preservation,
    )

    before = extract_protected_tokens("Increase of 15% observed.")
    after = extract_protected_tokens("Increase of 51% observed.")
    assert not validate_preservation(before, after).ok


def test_preservation_passes_when_preserved():
    from app.domain.humanization_preservation import (
        extract_protected_tokens,
        validate_preservation,
    )

    before = extract_protected_tokens("The findings [E1] show 42%.")
    after = extract_protected_tokens("Findings [E1] indicate 42%.")
    assert validate_preservation(before, after).ok
