"""M40 — report-scoped durable Agent Runtime API."""
from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.rate_limit_deps import enforce_user_rate_limit
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.models.agent_runtime import (
    AgentRuntimeCheckpoint,
    AgentRuntimeEvent,
    AgentRuntimeMessage,
    AgentRuntimeSession,
    AgentRuntimeToolCall,
)
from app.db.models.user import User
from app.db.session import SessionLocal, get_db
from app.domain.jobs import JobTypes
from app.schemas.agent_runtime import (
    AgentRuntimeMessageCreate,
    AgentRuntimeMessageListResponse,
    AgentRuntimeMessageRead,
    AgentRuntimeCheckpointListResponse,
    AgentRuntimeCheckpointRead,
    AgentRuntimeSessionCreate,
    AgentRuntimeSessionRead,
    AgentRuntimeToolCallDecision,
    AgentRuntimeToolCallListResponse,
    AgentRuntimeToolCallRead,
    AgentRuntimeTurnAccepted,
)
from app.schemas.orchestration import build_orchestration_output_preview
from app.services import agent_runtime as runtime_service
from app.services.agent_runtime_tools import (
    get_agent_tool_spec,
    validate_agent_tool_arguments,
)
from app.services.jobs import enqueue_job

router = APIRouter(prefix="/reports", tags=["agent-runtime"])


class AgentRuntimeDisabled(AppError):
    code = "AGENT_RUNTIME_DISABLED"
    status_code = 404
    message = "Agent Runtime is not enabled."


class AgentRuntimeBusy(AppError):
    code = "AGENT_RUNTIME_BUSY"
    status_code = 409
    message = "This research session already has a turn in progress."


class AgentRuntimeToolConflict(AppError):
    code = "AGENT_RUNTIME_TOOL_CONFLICT"
    status_code = 409
    message = "This tool request is no longer awaiting a decision."


def _require_enabled() -> None:
    if not get_settings().agent_runtime_enabled:
        raise AgentRuntimeDisabled()


@router.post(
    "/{report_id}/agent-runtime/sessions",
    response_model=AgentRuntimeSessionRead,
    status_code=201,
    dependencies=[
        Depends(
            enforce_user_rate_limit(
                "agent_runtime_session",
                setting_name="rate_limit_enqueue_per_minute",
            )
        )
    ],
)
def create_agent_session(
    report_id: uuid.UUID,
    body: AgentRuntimeSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRuntimeSession:
    _require_enabled()
    return runtime_service.create_session(
        db,
        user_id=current_user.id,
        report_id=report_id,
        title=body.title,
    )


@router.get(
    "/{report_id}/agent-runtime/sessions",
    response_model=list[AgentRuntimeSessionRead],
)
def list_agent_sessions(
    report_id: uuid.UUID,
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgentRuntimeSession]:
    _require_enabled()
    return runtime_service.list_sessions(
        db,
        user_id=current_user.id,
        report_id=report_id,
        limit=limit,
    )


@router.get(
    "/{report_id}/agent-runtime/sessions/{session_id}",
    response_model=AgentRuntimeSessionRead,
)
def get_agent_session(
    report_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRuntimeSession:
    _require_enabled()
    return runtime_service.get_owned_session(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
    )


@router.get(
    "/{report_id}/agent-runtime/sessions/{session_id}/messages",
    response_model=AgentRuntimeMessageListResponse,
)
def list_agent_messages(
    report_id: uuid.UUID,
    session_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRuntimeMessageListResponse:
    _require_enabled()
    items, total = runtime_service.list_messages(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
        limit=limit,
    )
    return AgentRuntimeMessageListResponse(
        items=[AgentRuntimeMessageRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
    )


@router.post(
    "/{report_id}/agent-runtime/sessions/{session_id}/messages",
    response_model=AgentRuntimeTurnAccepted,
    status_code=202,
    dependencies=[
        Depends(
            enforce_user_rate_limit(
                "agent_runtime_turn",
                setting_name="rate_limit_enqueue_per_minute",
            )
        )
    ],
)
def enqueue_agent_message(
    report_id: uuid.UUID,
    session_id: uuid.UUID,
    body: AgentRuntimeMessageCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRuntimeTurnAccepted:
    _require_enabled()
    session = runtime_service.get_owned_session(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
        lock=True,
    )
    if session.status in {"queued", "running", "awaiting_approval", "archived"}:
        raise AgentRuntimeBusy()
    if session.next_sequence >= 2_000_000_000:
        raise AppError("session message limit reached", code="AGENT_RUNTIME_LIMIT")

    user_message = AgentRuntimeMessage(
        session_id=session.id,
        sequence=session.next_sequence,
        role="user",
        content=body.content,
        evidence_refs=[],
    )
    db.add(user_message)
    session.next_sequence += 1
    session.status = "queued"
    session.active_job_id = None
    session.last_error_code = None
    session.last_message_at = datetime.now(UTC)
    session.revision += 1
    settings = get_settings()
    try:
        queued = enqueue_job(
            db,
            job_type=JobTypes.AGENT_RUNTIME_TURN,
            payload={
                "session_id": str(session.id),
                "report_id": str(report_id),
                "user_id": str(current_user.id),
                "user_message_id": str(user_message.id),
            },
            idempotency_key=f"agent-runtime:{session.id}:{user_message.id}",
            report_id=report_id,
            user_id=current_user.id,
            max_attempts=settings.orchestration_job_max_attempts,
        )
    except Exception:
        db.rollback()
        raise

    db.refresh(session)
    db.refresh(user_message)
    current = runtime_service.get_owned_session(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session.id,
        lock=True,
    )
    if current.status in {"queued", "running"} and current.active_job_id is None:
        current.active_job_id = queued.job.id
        current.revision += 1
        db.commit()
    response.status_code = 202
    return AgentRuntimeTurnAccepted(
        status=current.status,
        session_id=session.id,
        job_id=queued.job.id,
        user_message_id=user_message.id,
        revision=current.revision,
    )



def _read_agent_tool_call(
    tool_call: AgentRuntimeToolCall,
) -> AgentRuntimeToolCallRead:
    return AgentRuntimeToolCallRead(
        id=tool_call.id,
        session_id=tool_call.session_id,
        user_message_id=tool_call.user_message_id,
        tool_key=tool_call.tool_key,
        tool_version=tool_call.tool_version,
        tool_description=tool_call.tool_description,
        reason=tool_call.reason,
        arguments=dict(tool_call.arguments or {}),
        status=tool_call.status,
        output_preview=build_orchestration_output_preview(
            tool_call.output_snapshot
        ),
        error_code=tool_call.error_code,
        created_at=tool_call.created_at,
        approved_at=tool_call.approved_at,
        rejected_at=tool_call.rejected_at,
        completed_at=tool_call.completed_at,
    )


def _get_owned_tool_call(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    session_id: uuid.UUID,
    tool_call_id: uuid.UUID,
    lock: bool = False,
) -> AgentRuntimeToolCall:
    statement = select(AgentRuntimeToolCall).where(
        AgentRuntimeToolCall.id == tool_call_id,
        AgentRuntimeToolCall.session_id == session_id,
        AgentRuntimeToolCall.user_id == user_id,
        AgentRuntimeToolCall.report_id == report_id,
    )
    if lock:
        statement = statement.with_for_update()
    tool_call = db.execute(statement).scalar_one_or_none()
    if tool_call is None:
        raise AppError("tool request not found", code="AGENT_RUNTIME_TOOL_NOT_FOUND")
    return tool_call


@router.get(
    "/{report_id}/agent-runtime/sessions/{session_id}/tool-calls",
    response_model=AgentRuntimeToolCallListResponse,
)
def list_agent_tool_calls(
    report_id: uuid.UUID,
    session_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRuntimeToolCallListResponse:
    _require_enabled()
    runtime_service.get_owned_session(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
    )
    rows = db.execute(
        select(AgentRuntimeToolCall)
        .where(
            AgentRuntimeToolCall.session_id == session_id,
            AgentRuntimeToolCall.user_id == current_user.id,
            AgentRuntimeToolCall.report_id == report_id,
        )
        .order_by(
            AgentRuntimeToolCall.created_at.desc(),
            AgentRuntimeToolCall.id.desc(),
        )
        .limit(limit)
    ).scalars().all()
    return AgentRuntimeToolCallListResponse(
        items=[_read_agent_tool_call(row) for row in rows],
        limit=limit,
    )


@router.post(
    "/{report_id}/agent-runtime/sessions/{session_id}/tool-calls/{tool_call_id}/approve",
    response_model=AgentRuntimeToolCallDecision,
    status_code=202,
    dependencies=[
        Depends(
            enforce_user_rate_limit(
                "agent_runtime_tool_approval",
                setting_name="rate_limit_enqueue_per_minute",
            )
        )
    ],
)
def approve_agent_tool_call(
    report_id: uuid.UUID,
    session_id: uuid.UUID,
    tool_call_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRuntimeToolCallDecision:
    _require_enabled()
    session = runtime_service.get_owned_session(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
        lock=True,
    )
    tool_call = _get_owned_tool_call(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
        tool_call_id=tool_call_id,
        lock=True,
    )
    if session.status != "awaiting_approval" or tool_call.status != "pending":
        raise AgentRuntimeToolConflict()
    spec = get_agent_tool_spec(tool_call.tool_key)
    if spec.version != tool_call.tool_version:
        raise AgentRuntimeToolConflict()
    arguments = validate_agent_tool_arguments(spec, dict(tool_call.arguments or {}))

    # enqueue_job commits its Session. Record approval in the transaction it
    # commits, so a concurrent reject/approve cannot pass the pending-state test.
    tool_call.arguments = arguments
    tool_call.status = "queued"
    tool_call.approved_by_user_id = current_user.id
    tool_call.approved_at = datetime.now(UTC)
    tool_call.job_id = None
    tool_call.error_code = None
    tool_call.error_message = None
    session.status = "queued"
    session.active_job_id = None
    session.last_error_code = None
    session.revision += 1

    queued = enqueue_job(
        db,
        job_type=JobTypes.AGENT_RUNTIME_TURN,
        payload={
            "action": "execute_tool",
            "tool_call_id": str(tool_call.id),
            "session_id": str(session.id),
            "report_id": str(report_id),
            "user_id": str(current_user.id),
        },
        idempotency_key=f"agent-runtime-tool:{tool_call.id}",
        report_id=report_id,
        user_id=current_user.id,
        max_attempts=1,
    )
    # enqueue_job returns an existing idempotent job without committing.
    db.commit()
    db.refresh(session)
    db.refresh(tool_call)
    if session.status == "queued" and session.active_job_id is None:
        session.active_job_id = queued.job.id
        session.revision += 1
    if tool_call.status == "queued" and tool_call.job_id is None:
        tool_call.job_id = queued.job.id
    db.commit()
    return AgentRuntimeToolCallDecision(
        status="queued",
        tool_call_id=tool_call.id,
        session_id=session.id,
        job_id=queued.job.id,
    )


@router.post(
    "/{report_id}/agent-runtime/sessions/{session_id}/tool-calls/{tool_call_id}/reject",
    response_model=AgentRuntimeToolCallDecision,
    dependencies=[
        Depends(
            enforce_user_rate_limit(
                "agent_runtime_tool_approval",
                setting_name="rate_limit_enqueue_per_minute",
            )
        )
    ],
)
def reject_agent_tool_call(
    report_id: uuid.UUID,
    session_id: uuid.UUID,
    tool_call_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRuntimeToolCallDecision:
    _require_enabled()
    session = runtime_service.get_owned_session(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
        lock=True,
    )
    tool_call = _get_owned_tool_call(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
        tool_call_id=tool_call_id,
        lock=True,
    )
    if session.status != "awaiting_approval" or tool_call.status != "pending":
        raise AgentRuntimeToolConflict()

    tool_call.status = "rejected"
    tool_call.rejected_by_user_id = current_user.id
    tool_call.rejected_at = datetime.now(UTC)
    session.status = "idle"
    session.active_job_id = None
    session.last_error_code = None
    session.revision += 1
    session.last_message_at = datetime.now(UTC)
    db.add(
        AgentRuntimeMessage(
            session_id=session.id,
            sequence=session.next_sequence,
            role="assistant",
            content=f"Execution request for '{tool_call.tool_key}' was rejected.",
            evidence_refs=[],
            in_reply_to_message_id=tool_call.user_message_id,
        )
    )
    session.next_sequence += 1
    db.commit()
    return AgentRuntimeToolCallDecision(
        status="rejected",
        tool_call_id=tool_call.id,
        session_id=session.id,
    )


@router.get(
    "/{report_id}/agent-runtime/sessions/{session_id}/events",
    response_class=StreamingResponse,
)
def stream_agent_events(
    report_id: uuid.UUID,
    session_id: uuid.UUID,
    after: int | None = Query(default=None, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Replay persisted session events as authenticated server-sent events."""
    _require_enabled()
    initial = runtime_service.get_owned_session(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
    )
    cursor: int
    if last_event_id is not None:
        try:
            cursor = int(last_event_id)
        except ValueError as exc:
            raise AppError("invalid Last-Event-ID", code="AGENT_RUNTIME_EVENT_CURSOR") from exc
        if cursor < 0:
            raise AppError("invalid Last-Event-ID", code="AGENT_RUNTIME_EVENT_CURSOR")
    elif after is not None:
        cursor = after
    elif initial.status in {"queued", "running"}:
        with SessionLocal() as stream_db:
            latest_start = stream_db.execute(
                select(AgentRuntimeEvent.sequence)
                .where(
                    AgentRuntimeEvent.session_id == session_id,
                    AgentRuntimeEvent.event_type == "turn_started",
                )
                .order_by(AgentRuntimeEvent.sequence.desc())
                .limit(1)
            ).scalar_one_or_none()
        cursor = max(0, int(latest_start or initial.next_event_sequence) - (1 if latest_start else 0))
    else:
        cursor = initial.next_event_sequence

    def event_body():
        nonlocal cursor
        heartbeat_at = time.monotonic()
        terminal_events = {
            "turn_completed",
            "tool_approval_required",
            "turn_failed",
        }
        while True:
            with SessionLocal() as stream_db:
                active = runtime_service.get_owned_session(
                    stream_db,
                    user_id=current_user.id,
                    report_id=report_id,
                    session_id=session_id,
                )
                events = runtime_service.list_events_after(
                    stream_db,
                    session_id=session_id,
                    after_sequence=cursor,
                    limit=100,
                )
                terminal_status = active.status not in {"queued", "running"}
                terminal_event_seen = False
                for event in events:
                    payload = {
                        "id": event.sequence,
                        "type": event.event_type,
                        "payload": dict(event.payload or {}),
                        "created_at": event.created_at.isoformat(),
                    }
                    yield (
                        f"id: {event.sequence}\n"
                        "data: "
                        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                        + "\n\n"
                    )
                    cursor = event.sequence
                    if event.event_type in terminal_events:
                        terminal_event_seen = True
            if terminal_event_seen or (terminal_status and not events):
                break
            if not events and time.monotonic() - heartbeat_at >= 15:
                yield ": keep-alive\\n\\n"
                heartbeat_at = time.monotonic()
            time.sleep(0.4)

    return StreamingResponse(
        event_body(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{report_id}/agent-runtime/sessions/{session_id}/checkpoints",
    response_model=AgentRuntimeCheckpointListResponse,
)
def list_agent_checkpoints(
    report_id: uuid.UUID,
    session_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRuntimeCheckpointListResponse:
    _require_enabled()
    items, total = runtime_service.list_checkpoints(
        db,
        user_id=current_user.id,
        report_id=report_id,
        session_id=session_id,
        limit=limit,
    )
    return AgentRuntimeCheckpointListResponse(
        items=[AgentRuntimeCheckpointRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
    )
