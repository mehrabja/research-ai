import pytest

from app.domain.humanization import (
    HumanizationLayer,
    HumanizationPolicy,
    HumanizationStage,
    InvalidHumanizationPayloadError,
    build_humanization_job_idempotency_key,
    build_rewrite_idempotency_key,
    default_pre_translation_policy,
    sha256_hex,
)


def test_default_order():
    p = default_pre_translation_policy()
    assert p.enabled_layers == (HumanizationLayer.L1, HumanizationLayer.L2, HumanizationLayer.L3)
    assert p.stage == HumanizationStage.PRE_TRANSLATION


def test_duplicates_rejected():
    with pytest.raises(InvalidHumanizationPayloadError):
        HumanizationPolicy(
            version="m14.1", stage=HumanizationStage.PRE_TRANSLATION,
            enabled_layers=(HumanizationLayer.L1, HumanizationLayer.L1),
            max_segments=1, max_total_tokens=1, max_segment_chars=1,
            allow_partial=False, temperature=0.4, max_output_tokens=1,
            max_preservation_retries=0,
        )


def test_bad_order_rejected():
    with pytest.raises(InvalidHumanizationPayloadError):
        HumanizationPolicy(
            version="m14.1", stage=HumanizationStage.PRE_TRANSLATION,
            enabled_layers=(HumanizationLayer.L2, HumanizationLayer.L1),
            max_segments=1, max_total_tokens=1, max_segment_chars=1,
            allow_partial=False, temperature=0.4, max_output_tokens=1,
            max_preservation_retries=0,
        )


def test_roundtrip():
    p = default_pre_translation_policy()
    assert HumanizationPolicy.from_mapping(p.to_jsonable()) == p


def test_keys():
    assert build_humanization_job_idempotency_key(
        report_id="r", version_id="v", detection_run_id="d", policy_version="m14.1"
    ) == "humanize_report:r:v:d:m14.1"
    assert build_rewrite_idempotency_key(
        job_id="j", version_id="v", segment_id="s", layer="L1", policy_version="m14.1"
    ) == "humanize:j:v:s:L1:m14.1"


def test_sha():
    assert sha256_hex("a") == sha256_hex("a")
    assert sha256_hex("a") != sha256_hex("a ")
