"""M14/M17 — Humanization domain (pure: no SQLAlchemy / FastAPI / httpx)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

DEFAULT_POLICY_VERSION = "m14.1"
DEFAULT_POST_TRANSLATION_POLICY_VERSION = "m17.1"
DETECTION_STATUS_COMPLETED = "completed"


class HumanizationStage(StrEnum):
    PRE_TRANSLATION = "pre_translation"
    POST_TRANSLATION = "post_translation"


class HumanizationStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    BUDGET_EXCEEDED = "budget_exceeded"
    FAILED = "failed"


class HumanizationLayer(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"

    @classmethod
    def all_ordered(cls) -> tuple[HumanizationLayer, ...]:
        return (cls.L1, cls.L2, cls.L3, cls.L4)

    @classmethod
    def pre_translation_ordered(cls) -> tuple[HumanizationLayer, ...]:
        return (cls.L1, cls.L2, cls.L3)

    @classmethod
    def post_translation_ordered(cls) -> tuple[HumanizationLayer, ...]:
        return (cls.L4,)

    @classmethod
    def ordered(cls) -> tuple[HumanizationLayer, ...]:
        return cls.pre_translation_ordered()


class HumanizationError(Exception): ...
class InvalidHumanizationPayloadError(HumanizationError): ...
class HumanizationAlreadyCompletedError(HumanizationError): ...
class HumanizationAlreadyRunningError(HumanizationError): ...
class HumanizationNoSegmentDataError(HumanizationError): ...
class HumanizationSegmentMappingError(HumanizationError): ...
class HumanizationSegmentTooLargeError(HumanizationError): ...
class HumanizationPreservationError(HumanizationError): ...
class HumanizationBudgetExceededError(HumanizationError): ...
class HumanizationStateError(HumanizationError): ...
class HumanizationOwnershipLostError(HumanizationStateError): ...


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_STAGE_NEXT_STATUS: Mapping[str, str] = {
    HumanizationStage.PRE_TRANSLATION.value: "pre_translation_review",
    HumanizationStage.POST_TRANSLATION.value: "converging",
}


def next_status_for_stage(stage: HumanizationStage | str) -> str:
    s = stage.value if isinstance(stage, HumanizationStage) else str(stage)
    result = _STAGE_NEXT_STATUS.get(s)
    if result is None:
        raise InvalidHumanizationPayloadError(
            f"no next_status mapping for stage {s!r}"
        )
    return result


def _canonical_layers_for_stage(
    stage: HumanizationStage,
) -> tuple[HumanizationLayer, ...]:
    if stage is HumanizationStage.PRE_TRANSLATION:
        return HumanizationLayer.pre_translation_ordered()
    if stage is HumanizationStage.POST_TRANSLATION:
        return HumanizationLayer.post_translation_ordered()
    raise InvalidHumanizationPayloadError(f"unknown stage {stage!r}")


@dataclass(frozen=True)
class HumanizationPolicy:
    version: str
    stage: HumanizationStage
    enabled_layers: tuple[HumanizationLayer, ...]
    max_segments: int
    max_total_tokens: int
    max_segment_chars: int
    allow_partial: bool
    temperature: float
    max_output_tokens: int
    max_preservation_retries: int
    job_id: str | None = None

    def __post_init__(self) -> None:
        if not self.version:
            raise InvalidHumanizationPayloadError("policy.version must be non-empty")
        if self.max_segments <= 0:
            raise InvalidHumanizationPayloadError("max_segments must be > 0")
        if self.max_total_tokens <= 0:
            raise InvalidHumanizationPayloadError("max_total_tokens must be > 0")
        if self.max_segment_chars <= 0:
            raise InvalidHumanizationPayloadError("max_segment_chars must be > 0")
        if not 0.0 <= self.temperature <= 2.0:
            raise InvalidHumanizationPayloadError("temperature out of range")
        if self.max_output_tokens <= 0:
            raise InvalidHumanizationPayloadError("max_output_tokens must be > 0")
        if self.max_preservation_retries < 0:
            raise InvalidHumanizationPayloadError(
                "max_preservation_retries must be >= 0"
            )
        if not self.enabled_layers:
            raise InvalidHumanizationPayloadError(
                "enabled_layers must be non-empty"
            )
        canonical = _canonical_layers_for_stage(self.stage)
        seen = set(self.enabled_layers)
        if len(seen) != len(self.enabled_layers):
            raise InvalidHumanizationPayloadError("duplicate layers")
        expected = tuple(lyr for lyr in canonical if lyr in seen)
        if self.enabled_layers != expected:
            raise InvalidHumanizationPayloadError(
                "enabled_layers must be in canonical order for stage "
                f"{self.stage.value}"
            )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "stage": self.stage.value,
            "enabled_layers": [lyr.value for lyr in self.enabled_layers],
            "max_segments": self.max_segments,
            "max_total_tokens": self.max_total_tokens,
            "max_segment_chars": self.max_segment_chars,
            "allow_partial": self.allow_partial,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "max_preservation_retries": self.max_preservation_retries,
            "job_id": self.job_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_jsonable(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> HumanizationPolicy:
        try:
            stage = HumanizationStage(str(data["stage"]))
            layers_raw = data["enabled_layers"]
            if not isinstance(layers_raw, (list, tuple)):
                raise ValueError("enabled_layers must be a sequence")
            layers = tuple(HumanizationLayer(str(x)) for x in layers_raw)
            return cls(
                version=str(data["version"]),
                stage=stage,
                enabled_layers=layers,
                max_segments=int(data["max_segments"]),
                max_total_tokens=int(data["max_total_tokens"]),
                max_segment_chars=int(data["max_segment_chars"]),
                allow_partial=bool(data["allow_partial"]),
                temperature=float(data["temperature"]),
                max_output_tokens=int(data["max_output_tokens"]),
                max_preservation_retries=int(data["max_preservation_retries"]),
                job_id=(str(data["job_id"]) if data.get("job_id") else None),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidHumanizationPayloadError(
                f"invalid HumanizationPolicy payload: {exc}"
            ) from exc


def default_pre_translation_policy(
    *,
    job_id: str | None = None,
    version: str = DEFAULT_POLICY_VERSION,
    max_segments: int = 50,
    max_total_tokens: int = 60_000,
    max_segment_chars: int = 4_000,
    allow_partial: bool = False,
    temperature: float = 0.4,
    max_output_tokens: int = 2_048,
    max_preservation_retries: int = 1,
) -> HumanizationPolicy:
    return HumanizationPolicy(
        version=version,
        stage=HumanizationStage.PRE_TRANSLATION,
        enabled_layers=HumanizationLayer.pre_translation_ordered(),
        max_segments=max_segments,
        max_total_tokens=max_total_tokens,
        max_segment_chars=max_segment_chars,
        allow_partial=allow_partial,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        max_preservation_retries=max_preservation_retries,
        job_id=job_id,
    )


def default_post_translation_policy(
    *,
    job_id: str | None = None,
    version: str = DEFAULT_POST_TRANSLATION_POLICY_VERSION,
    max_segments: int = 50,
    max_total_tokens: int = 60_000,
    max_segment_chars: int = 4_000,
    allow_partial: bool = False,
    temperature: float = 0.4,
    max_output_tokens: int = 2_048,
    max_preservation_retries: int = 1,
) -> HumanizationPolicy:
    return HumanizationPolicy(
        version=version,
        stage=HumanizationStage.POST_TRANSLATION,
        enabled_layers=HumanizationLayer.post_translation_ordered(),
        max_segments=max_segments,
        max_total_tokens=max_total_tokens,
        max_segment_chars=max_segment_chars,
        allow_partial=allow_partial,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        max_preservation_retries=max_preservation_retries,
        job_id=job_id,
    )


def build_humanization_job_idempotency_key(
    *,
    report_id: str,
    version_id: str,
    detection_run_id: str,
    policy_version: str,
) -> str:
    return f"humanize_report:{report_id}:{version_id}:{detection_run_id}:{policy_version}"


def build_rewrite_idempotency_key(
    *,
    job_id: str,
    version_id: str,
    segment_id: str,
    layer: HumanizationLayer | str,
    policy_version: str,
) -> str:
    layer_value = layer.value if isinstance(layer, HumanizationLayer) else str(layer)
    return f"humanize:{job_id}:{version_id}:{segment_id}:{layer_value}:{policy_version}"


def build_post_translation_rewrite_idempotency_key(
    *,
    job_id: str,
    translation_version_id: str,
    translated_version_id: str,
    segment_id: str,
    layer: HumanizationLayer | str,
    policy_version: str,
) -> str:
    layer_value = layer.value if isinstance(layer, HumanizationLayer) else str(layer)
    return (
        f"humanize_post_translation:{job_id}:"
        f"{translation_version_id}:{translated_version_id}:"
        f"{segment_id}:{layer_value}:{policy_version}"
    )


def build_post_translation_humanization_job_idempotency_key(
    *,
    report_id: str,
    translation_run_id: str,
    translation_version_id: str,
    policy_version: str,
) -> str:
    return (
        f"humanize_post_translation:{report_id}:"
        f"{translation_run_id}:{translation_version_id}:{policy_version}"
    )
