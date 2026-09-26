"""M35 — Concrete tool implementations.

Each tool wraps an existing service. No business logic is duplicated.

Note: to avoid a circular import with registry.py, this module does
NOT import registry at top level. Registration is triggered by
``registry.py`` at the bottom of its module.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_TOOL_VERSION = "m35-tools-v1"


def _call_build_plan(
    db: Session, ctx: Any,
) -> dict[str, Any]:
    from app.services.research_planning import planner as planner_svc

    if ctx.user_id is None:
        raise ValueError("build_plan requires user_id")
    result = planner_svc.generate_research_plan(
        db,
        user_id=ctx.user_id,
        project_id=ctx.project_id,
    )
    return {
        "plan_id": str(getattr(result, "plan_id", None) or ""),
    }


def _call_technical_intelligence(
    db: Session, ctx: Any,
) -> dict[str, Any]:
    from app.services.technical_intelligence import (
        persistence as ti_persist,
    )

    persisted = ti_persist.run_m29_persisted(
        db, project_id=ctx.project_id, commit=False,
    )
    return {
        "run_id": str(persisted.run.id),
        "fact_count": int(persisted.run.fact_count or 0),
        "result_count": int(persisted.run.result_count or 0),
        "metric_count": int(persisted.run.metric_count or 0),
    }


def _call_generate_citations(
    db: Session, ctx: Any,
) -> dict[str, Any]:
    from app.services.citation import persistence as cit_persist

    manuscript_version_id = ctx.payload.get("manuscript_version_id")
    if manuscript_version_id is None:
        raise ValueError(
            "generate_citations requires manuscript_version_id"
        )
    persisted = cit_persist.run_citation_persisted(
        db,
        user_id=ctx.user_id,
        report_id=ctx.report_id,
        manuscript_version_id=_uuid.UUID(str(manuscript_version_id)),
        commit=False,
    )
    return {
        "run_id": str(persisted.run.id),
        "claim_count": int(persisted.run.claim_count or 0),
        "citation_count": int(persisted.run.citation_count or 0),
    }


def _call_academic_qa(
    db: Session, ctx: Any,
) -> dict[str, Any]:
    from app.services.academic_qa import persistence as qa_persist

    manuscript_version_id = ctx.payload.get("manuscript_version_id")
    if manuscript_version_id is None:
        raise ValueError(
            "academic_qa requires manuscript_version_id"
        )
    persisted = qa_persist.run_m31_persisted(
        db,
        report_id=ctx.report_id,
        manuscript_version_id=_uuid.UUID(str(manuscript_version_id)),
        commit=False,
    )
    return {
        "run_id": str(persisted.run.id),
        "gate": persisted.run.gate,
        "finding_count": int(persisted.run.finding_count or 0),
        "blocking_count": int(persisted.run.blocking_count or 0),
    }


def _call_humanize(
    db: Session, ctx: Any,
) -> dict[str, Any]:
    from app.services.manuscript_humanization import (
        persistence as mh_persist,
    )

    manuscript_version_id = ctx.payload.get("manuscript_version_id")
    mode = ctx.payload.get("mode", "academic")
    if manuscript_version_id is None:
        raise ValueError(
            "humanize requires manuscript_version_id"
        )
    persisted = mh_persist.run_m32_persisted(
        db,
        report_id=ctx.report_id,
        manuscript_version_id=_uuid.UUID(str(manuscript_version_id)),
        mode=mode,
        commit=False,
    )
    return {
        "run_id": str(persisted.run.id),
        "gate": persisted.run.gate,
    }


def _call_target_compliance(
    db: Session, ctx: Any,
) -> dict[str, Any]:
    from app.services.publication import persistence as pub_persist

    manuscript_version_id = ctx.payload.get("manuscript_version_id")
    target_id = ctx.payload.get("target_id")
    if manuscript_version_id is None or target_id is None:
        raise ValueError(
            "target_compliance requires manuscript_version_id "
            "and target_id"
        )
    persisted = pub_persist.run_m33_persisted(
        db,
        report_id=ctx.report_id,
        manuscript_version_id=_uuid.UUID(str(manuscript_version_id)),
        target_id=_uuid.UUID(str(target_id)),
        commit=False,
    )
    return {
        "run_id": str(persisted.run.id),
        "gate": persisted.run.gate,
        "finding_count": int(persisted.run.finding_count or 0),
    }
def _call_manuscript_prose_generate(
    db: Session, ctx: Any,
) -> dict[str, Any]:
    from app.services.manuscript_prose import persistence as mp_persist

    base_manuscript_version_id = ctx.payload.get(
        "base_manuscript_version_id"
    ) or ctx.payload.get("manuscript_version_id")
    if base_manuscript_version_id is None:
        raise ValueError(
            "manuscript_prose_generate requires "
            "base_manuscript_version_id"
        )
    mode = ctx.payload.get("mode")
    persisted = mp_persist.run_m28_5_persisted(
        db,
        report_id=ctx.report_id,
        base_manuscript_version_id=_uuid.UUID(
            str(base_manuscript_version_id)
        ),
        mode=mode,
        commit=False,
    )
    return {
        "run_id": str(persisted.run.id),
        "section_count": int(persisted.run.section_count or 0),
        "word_count": int(persisted.run.word_count or 0),
    }

def _register_all() -> None:
    from app.services.orchestration.registry import (
        ToolSpec,
        register_tool,
    )

    register_tool(
        ToolSpec(
            key="build_plan",
            version=_TOOL_VERSION,
            description="Build a research plan for the project.",
            permission="write",
            deterministic=True,
            timeout_seconds=120,
            max_attempts=3,
            input_schema={"type": "object", "properties": {}},
            output_schema={
                "type": "object",
                "properties": {"plan_id": {"type": "string"}},
            },
            idempotent=True,
        ),
        _call_build_plan,
    )
    register_tool(
        ToolSpec(
            key="technical_intelligence",
            version=_TOOL_VERSION,
            description="Run M29 technical intelligence for the project.",
            permission="write",
            deterministic=True,
            timeout_seconds=180,
            max_attempts=3,
            input_schema={"type": "object", "properties": {}},
            output_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "fact_count": {"type": "integer"},
                },
            },
            idempotent=True,
        ),
        _call_technical_intelligence,
    )
    register_tool(
        ToolSpec(
            key="generate_citations",
            version=_TOOL_VERSION,
            description=(
                "Run M30 citation engine on a manuscript version."
            ),
            permission="write",
            deterministic=True,
            timeout_seconds=180,
            max_attempts=3,
            input_schema={
                "type": "object",
                "required": ["manuscript_version_id"],
                "properties": {
                    "manuscript_version_id": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "claim_count": {"type": "integer"},
                },
            },
            idempotent=True,
        ),
        _call_generate_citations,
    )
    register_tool(
        ToolSpec(
            key="academic_qa",
            version=_TOOL_VERSION,
            description=(
                "Run M31 academic QA on a manuscript version."
            ),
            permission="write",
            deterministic=True,
            timeout_seconds=180,
            max_attempts=3,
            input_schema={
                "type": "object",
                "required": ["manuscript_version_id"],
                "properties": {
                    "manuscript_version_id": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "gate": {"type": "string"},
                },
            },
            idempotent=True,
        ),
        _call_academic_qa,
    )
    register_tool(
        ToolSpec(
            key="humanize",
            version=_TOOL_VERSION,
            description="Run M32 manuscript humanization.",
            permission="write",
            deterministic=False,
            timeout_seconds=600,
            max_attempts=2,
            input_schema={
                "type": "object",
                "required": ["manuscript_version_id"],
                "properties": {
                    "manuscript_version_id": {"type": "string"},
                    "mode": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "gate": {"type": "string"},
                },
            },
            idempotent=True,
        ),
        _call_humanize,
    )
    register_tool(
        ToolSpec(
            key="manuscript_prose_generate",
            version=_TOOL_VERSION,
            description=(
                "Generate evidence-grounded manuscript prose for "
                "the base manuscript version."
            ),
            permission="write",
            deterministic=True,
            timeout_seconds=300,
            max_attempts=2,
            input_schema={
                "type": "object",
                "required": ["base_manuscript_version_id"],
                "properties": {
                    "base_manuscript_version_id": {"type": "string"},
                    "mode": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "section_count": {"type": "integer"},
                },
            },
            idempotent=True,
        ),
        _call_manuscript_prose_generate,
    )
    register_tool(
        ToolSpec(
            key="target_compliance",
            version=_TOOL_VERSION,
            description="Run M33 target compliance.",
            permission="write",
            deterministic=True,
            timeout_seconds=120,
            max_attempts=3,
            input_schema={
                "type": "object",
                "required": [
                    "manuscript_version_id",
                    "target_id",
                ],
                "properties": {
                    "manuscript_version_id": {"type": "string"},
                    "target_id": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "gate": {"type": "string"},
                },
            },
            idempotent=True,
        ),
        _call_target_compliance,
    )


_register_all()

__all__ = ["_TOOL_VERSION"]
