"""M40 — durable, report-scoped Agent Runtime turn handler."""
from __future__ import annotations

import logging
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.agent_runtime import AgentRuntimeMessage, AgentRuntimeSession
from app.db.models.jobs import Job
from app.db.models.project import Project
from app.db.models.source import Source
from app.db.session import SessionLocal
from app.domain.jobs import JobContext, JobTypes
from app.services import ai_metering, retrieval
from app.services.agent_runtime import (
    build_agent_runtime_prompts,
    constrain_citations,
    recent_history,
)
from app.services.embedding_profile import get_current_embedding_profile
from app.services.generation_profile import (
    build_generation_provider,
    get_current_generation_profile,
)
from app.services.reports import get_report

logger = logging.getLogger(__name__)
_PROTOCOL_VERSION = "m40-agent-runtime-v1"
_MAX_EVIDENCE_ITEMS = 8
_MAX_EVIDENCE_CHARS = 1200


def _uuid(value: Any, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"agent runtime payload has invalid {field}") from exc


def _load_evidence(
    db,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    query: str,
) -> list[dict[str, Any]]:
    profile = get_current_embedding_profile()
    try:
        chunks, _coverage = retrieval.retrieve(
            db,
            user_id=user_id,
            report_id=report_id,
            query=query[:500],
            top_k=_MAX_EVIDENCE_ITEMS,
            mode="lexical",
            algorithm="ann",
            source_ids=None,
            # Lexical retrieval does not invoke the provider.
            provider=None,  # type: ignore[arg-type]
            profile=profile,
        )
    except Exception as exc:
        from app.core.exceptions import EmbeddingsNotReadyError, RetrievalConfigurationError
        if isinstance(exc, (EmbeddingsNotReadyError, RetrievalConfigurationError)):
            logger.info(
                "agent_runtime_no_indexed_evidence report_id=%s reason=%s",
                report_id,
                type(exc).__name__,
            )
            return []
        raise

    source_ids = {chunk.source_id for chunk in chunks}
    if not source_ids:
        return []
    sources = db.execute(
        select(Source).where(
            Source.report_id == report_id,
            Source.id.in_(source_ids),
        )
    ).scalars().all()
    by_id = {source.id: source for source in sources}
    evidence: list[dict[str, Any]] = []
    for chunk in chunks:
        source = by_id.get(chunk.source_id)
        if source is None:
            continue
        evidence.append({
            "label": f"E{len(evidence) + 1}",
            "reference": chunk.evidence_id(),
            "source_id": str(source.id),
            "chunk_id": str(chunk.chunk_id),
            "title": (source.title or "Untitled source")[:300],
            "doi": source.doi,
            "url": source.url,
            "year": source.year,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "retrieval_rank": chunk.final_rank,
            "excerpt": (chunk.content or "")[:_MAX_EVIDENCE_CHARS],
        })
        if len(evidence) >= _MAX_EVIDENCE_ITEMS:
            break
    return evidence


def handle_agent_runtime_turn(ctx: JobContext) -> dict[str, Any]:
    payload = dict(ctx.payload or {})
    session_id = _uuid(payload.get("session_id"), "session_id")
    report_id = _uuid(payload.get("report_id"), "report_id")
    user_message_id = _uuid(payload.get("user_message_id"), "user_message_id")
    user_id = _uuid(payload.get("user_id"), "user_id")
    settings = get_settings()
    session_snapshot: dict[str, Any]

    with SessionLocal() as db:
        job = db.execute(
            select(Job).where(Job.id == ctx.job_id).with_for_update()
        ).scalar_one_or_none()
        if (
            job is None
            or job.job_type != JobTypes.AGENT_RUNTIME_TURN
            or job.user_id != user_id
            or job.report_id != report_id
            or job.status != "processing"
            or job.worker_id != ctx.worker_id
            or job.attempt_count != ctx.attempt_count
        ):
            raise ValueError("agent runtime job ownership does not match payload")

        session = db.execute(
            select(AgentRuntimeSession)
            .where(
                AgentRuntimeSession.id == session_id,
                AgentRuntimeSession.user_id == user_id,
                AgentRuntimeSession.report_id == report_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if session is None:
            raise ValueError("agent runtime session is unavailable")
        if session.status == "archived":
            return {"status": "skipped", "reason": "session_archived"}
        if session.active_job_id not in (None, ctx.job_id):
            raise ValueError("agent runtime session is owned by another job")

        user_message = db.execute(
            select(AgentRuntimeMessage).where(
                AgentRuntimeMessage.id == user_message_id,
                AgentRuntimeMessage.session_id == session_id,
                AgentRuntimeMessage.role == "user",
            )
        ).scalar_one_or_none()
        if user_message is None:
            raise ValueError("agent runtime user message is unavailable")

        prior_reply = db.execute(
            select(AgentRuntimeMessage).where(
                AgentRuntimeMessage.in_reply_to_message_id == user_message_id
            )
        ).scalar_one_or_none()
        if prior_reply is not None:
            session.status = "idle"
            session.active_job_id = None
            session.last_error_code = None
            session.revision += 1
            db.commit()
            return {"status": "already_replied"}

        report = get_report(db, user_id=user_id, report_id=report_id)
        if report.project_id != session.project_id:
            raise ValueError("agent runtime report/project binding changed")
        project = db.get(Project, session.project_id) if session.project_id else None
        if session.project_id is not None and (
            project is None or project.user_id != user_id
        ):
            raise ValueError("agent runtime project is not accessible")
        if project is not None and project.workspace_id != session.workspace_id:
            raise ValueError("agent runtime workspace binding changed")

        session.status = "running"
        session.active_job_id = ctx.job_id
        session.last_error_code = None
        session.revision += 1
        db.commit()

        history = recent_history(
            db,
            session_id=session_id,
            before_sequence=user_message.sequence,
            limit=settings.agent_runtime_max_history_messages,
        )
        session_snapshot = {
            "workspace_id": session.workspace_id,
            "project_id": session.project_id,
            "topic": report.topic,
            "domain": report.domain,
            "message_id": user_message.id,
            "message_sequence": user_message.sequence,
            "content": user_message.content,
            "history": history,
        }

    with SessionLocal() as db:
        evidence = _load_evidence(
            db,
            user_id=user_id,
            report_id=report_id,
            query=session_snapshot["content"],
        )

    with SessionLocal() as db:
        current_job = db.execute(
            select(Job).where(Job.id == ctx.job_id).with_for_update()
        ).scalar_one_or_none()
        if (
            current_job is None
            or current_job.status != "processing"
            or current_job.worker_id != ctx.worker_id
            or current_job.attempt_count != ctx.attempt_count
        ):
            raise ValueError("agent runtime worker lease was lost before generation")

    system_prompt, user_prompt = build_agent_runtime_prompts(
        report_topic=session_snapshot["topic"],
        report_domain=session_snapshot["domain"],
        history=session_snapshot["history"],
        current_message=session_snapshot["content"],
        evidence=evidence,
        max_prompt_chars=settings.agent_runtime_max_prompt_chars,
    )
    profile = get_current_generation_profile()
        effective_profile = replace(
        profile,
        temperature=min(profile.temperature, 0.3),
        max_output_tokens=min(
            profile.max_output_tokens,
            settings.agent_runtime_max_output_tokens,
        ),
    )
    provider = build_generation_provider(effective_profile)
    result = ai_metering.execute_metered_provider_call(
        call=lambda: provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=effective_profile.temperature,
            max_output_tokens=effective_profile.max_output_tokens,
        ),
        workspace_id=session_snapshot["workspace_id"],
        user_id=user_id,
        operation="agent_runtime_turn",
        capability="generation",
        provider=provider,
        model=effective_profile.model,
        project_id=session_snapshot["project_id"],
        report_id=report_id,
        job_id=ctx.job_id,
        request_id=f"agent-runtime:{session_id}:{user_message_id}",
        input_units=lambda value: value.input_tokens,
        output_units=lambda value: value.output_tokens,
        metadata={
            "protocol": _PROTOCOL_VERSION,
            "session_id": str(session_id),
            "user_message_id": str(user_message_id),
            "evidence_count": len(evidence),
            "execution_mode": "evidence-grounded-no-tools",
        },
    )
    answer, cited_evidence = constrain_citations(result.text, evidence)
    if not answer.strip():
        raise ValueError("generation provider returned an empty agent response")

    with SessionLocal() as db:
        current_job = db.get(Job, ctx.job_id)
        if (
            current_job is None
            or current_job.status != "processing"
            or current_job.worker_id != ctx.worker_id
            or current_job.attempt_count != ctx.attempt_count
        ):
            raise ValueError("agent runtime worker lease was lost before reply persistence")
        session = db.execute(
            select(AgentRuntimeSession)
            .where(
                AgentRuntimeSession.id == session_id,
                AgentRuntimeSession.user_id == user_id,
                AgentRuntimeSession.report_id == report_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if session is None:
            raise ValueError("agent runtime session disappeared before persistence")
        if session.active_job_id not in (None, ctx.job_id):
            raise ValueError("agent runtime session lease changed before persistence")
        existing = db.execute(
            select(AgentRuntimeMessage).where(
                AgentRuntimeMessage.in_reply_to_message_id == user_message_id
            )
        ).scalar_one_or_none()
        if existing is None:
            reply = AgentRuntimeMessage(
                session_id=session_id,
                sequence=session.next_sequence,
                role="assistant",
                content=answer,
                evidence_refs=cited_evidence,
                in_reply_to_message_id=user_message_id,
                provider_name=result.provider,
                model_name=result.model,
                token_usage={
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "total_tokens": result.total_tokens,
                },
            )
            db.add(reply)
            session.next_sequence += 1
        session.status = "idle"
        session.active_job_id = None
        session.last_error_code = None
        session.last_message_at = datetime.now(UTC)
        session.revision += 1
        db.commit()

    return {
        "status": "completed",
        "session_id": str(session_id),
        "user_message_id": str(user_message_id),
        "evidence_count": len(evidence),
        "cited_evidence_count": len(cited_evidence),
        "provider": result.provider,
        "model": result.model,
    }


def mark_agent_runtime_turn_failed(ctx: JobContext, exc: BaseException) -> None:
    payload = dict(ctx.payload or {})
    session_id = _uuid(payload.get("session_id"), "session_id")
    user_id = _uuid(payload.get("user_id"), "user_id")
    report_id = _uuid(payload.get("report_id"), "report_id")
    with SessionLocal() as db:
        job = db.execute(
            select(Job).where(Job.id == ctx.job_id).with_for_update()
        ).scalar_one_or_none()
        if (
            job is None
            or job.status != "processing"
            or job.worker_id != ctx.worker_id
            or job.attempt_count != ctx.attempt_count
        ):
            return
        session = db.execute(
            select(AgentRuntimeSession)
            .where(
                AgentRuntimeSession.id == session_id,
                AgentRuntimeSession.user_id == user_id,
                AgentRuntimeSession.report_id == report_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if session is None or session.status == "archived":
            return
        if session.active_job_id not in (None, ctx.job_id):
            return
        from app.domain.jobs import RETRYABLE_ERROR_CODES
        from app.workers.classification import classify_exception

        error_code = classify_exception(exc)
        should_retry = (
            job is not None
            and error_code in RETRYABLE_ERROR_CODES
            and ctx.attempt_count < job.max_attempts
        )
        session.status = "queued" if should_retry else "failed"
        session.active_job_id = ctx.job_id if should_retry else None
        session.last_error_code = error_code[:80]
        session.revision += 1
        db.commit()


def safe_agent_runtime_handler(ctx: JobContext) -> dict[str, Any]:
    try:
        return handle_agent_runtime_turn(ctx)
    except Exception as exc:
        try:
            mark_agent_runtime_turn_failed(ctx, exc)
        except Exception:
            logger.exception(
                "agent_runtime_failure_state_persist_failed job_id=%s",
                ctx.job_id,
            )
        raise


__all__ = ["handle_agent_runtime_turn", "safe_agent_runtime_handler"]
