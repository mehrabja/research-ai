"""M40 — report-scoped durable Agent Runtime API."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.rate_limit_deps import enforce_user_rate_limit
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.models.agent_runtime import AgentRuntimeMessage, AgentRuntimeSession
from app.db.models.user import User
from app.db.session import get_db
from app.domain.jobs import JobTypes
from app.schemas.agent_runtime import (
    AgentRuntimeMessageCreate,
    AgentRuntimeMessageListResponse,
    AgentRuntimeMessageRead,
    AgentRuntimeSessionCreate,
    AgentRuntimeSessionRead,
    AgentRuntimeTurnAccepted,
)
from app.services import agent_runtime as runtime_service
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
    if session.status in {"queued", "running", "archived"}:
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
