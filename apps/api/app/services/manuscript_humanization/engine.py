"""M32 — Deterministic orchestrator. No persistence.

When prose is unavailable, returns a real result with
prose_available=False and no iterations.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ManuscriptHumanizationConfigurationInvalid
from app.domain.humanization_m32 import (
    HUMANIZATION_MODES,
    M32_PRESERVATION_VERSION,
    HumanizationGate,
    HumanizationMode,
    mode_policy,
)
from app.services.citation import prose as prose_svc


@dataclass
class M32Result:
    project_id: uuid.UUID
    report_id: uuid.UUID
    manuscript_id: uuid.UUID
    manuscript_version_id: uuid.UUID
    mode: str
    context_hash: str
    prose_available: bool
    iterations: int = 0
    preservation_ratio: float = 1.0
    gate: str = HumanizationGate.PASS.value
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0


def run_manuscript_humanization(
    db: Session,
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    mode: str,
    context_hash: str,
) -> M32Result:
    started = time.perf_counter()
    settings = get_settings()
    if not settings.manuscript_humanization_enabled:
        raise ManuscriptHumanizationConfigurationInvalid(
            "manuscript humanization is disabled"
        )
    if mode not in HUMANIZATION_MODES:
        raise ManuscriptHumanizationConfigurationInvalid(
            f"unknown humanization mode: {mode}"
        )

    warnings: list[str] = []
    policy = mode_policy(mode)

    prose = prose_svc.get_manuscript_prose(
        db, manuscript_version_id=manuscript_version_id,
    )
    prose_available = prose is not None and not prose.is_empty

    if not prose_available:
        warnings.append("manuscript_prose_not_available")
        return M32Result(
            project_id=project_id,
            report_id=report_id,
            manuscript_id=manuscript_id,
            manuscript_version_id=manuscript_version_id,
            mode=mode,
            context_hash=context_hash,
            prose_available=False,
            iterations=0,
            preservation_ratio=1.0,
            gate=HumanizationGate.PASS.value,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    # Prose is available but M32 rewrite provider is not wired yet:
    # be explicit and deterministic instead of fabricating.
    warnings.append(
        f"rewrite_provider_not_configured:mode={mode}:"
        f"preserve_min={policy['preserve_ratio_min']}"
    )
    return M32Result(
        project_id=project_id,
        report_id=report_id,
        manuscript_id=manuscript_id,
        manuscript_version_id=manuscript_version_id,
        mode=mode,
        context_hash=context_hash,
        prose_available=True,
        iterations=0,
        preservation_ratio=1.0,
        gate=HumanizationGate.PASS_WITH_WARNINGS.value,
        warnings=warnings,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


__all__ = [
    "M32Result",
    "run_manuscript_humanization",
    "M32_PRESERVATION_VERSION",
    "HumanizationMode",
]
