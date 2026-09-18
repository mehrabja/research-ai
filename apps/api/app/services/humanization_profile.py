"""M14 — Build HumanizationPolicy from application settings."""

from __future__ import annotations

from app.core.config import get_settings
from app.domain.humanization import (
    HumanizationLayer,
    HumanizationPolicy,
    HumanizationStage,
)


def build_policy_from_settings(
    *,
    job_id: str | None = None,
    version: str | None = None,
) -> HumanizationPolicy:
    settings = get_settings()
    return HumanizationPolicy(
        version=version or settings.humanization_policy_version,
        stage=HumanizationStage.PRE_TRANSLATION,
        enabled_layers=HumanizationLayer.ordered(),
        max_segments=settings.humanization_max_segments,
        max_total_tokens=settings.humanization_max_total_tokens,
        max_segment_chars=settings.humanization_max_segment_chars,
        allow_partial=settings.humanization_allow_partial,
        temperature=settings.humanization_temperature,
        max_output_tokens=settings.humanization_max_output_tokens,
        max_preservation_retries=settings.humanization_max_preservation_retries,
        job_id=job_id,
    )
def build_post_translation_policy_from_settings(
    *,
    job_id: str | None = None,
    version: str | None = None,
):
    from app.domain.humanization import (
        HumanizationLayer,
        HumanizationPolicy,
        HumanizationStage,
    )

    s = get_settings()
    return HumanizationPolicy(
        version=version or s.post_translation_humanization_policy_version,
        stage=HumanizationStage.POST_TRANSLATION,
        enabled_layers=HumanizationLayer.post_translation_ordered(),
        max_segments=s.post_translation_humanization_max_segments,
        max_total_tokens=s.post_translation_humanization_max_total_tokens,
        max_segment_chars=s.post_translation_humanization_max_segment_chars,
        allow_partial=False,
        temperature=s.post_translation_humanization_temperature,
        max_output_tokens=s.post_translation_humanization_max_output_tokens,
        max_preservation_retries=(
            s.post_translation_humanization_max_preservation_retries
        ),
        job_id=job_id,
    )
