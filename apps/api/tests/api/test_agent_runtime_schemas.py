from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.agent_runtime import (
    AgentRuntimeMessageCreate,
    AgentRuntimeSessionCreate,
    AgentRuntimeSessionRead,
)


def test_agent_runtime_message_rejects_blank_content() -> None:
    with pytest.raises(ValidationError):
        AgentRuntimeMessageCreate(content="   ")


def test_agent_runtime_message_normalizes_content() -> None:
    body = AgentRuntimeMessageCreate(content="  Explain this paper.  ")
    assert body.content == "Explain this paper."


def test_agent_runtime_session_title_normalizes_empty_value() -> None:
    body = AgentRuntimeSessionCreate(title="   ")
    assert body.title is None


def test_agent_runtime_session_schema_exposes_checkpoint_cursors() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    now = datetime.now(UTC)
    session = AgentRuntimeSessionRead(
        id=uuid4(),
        user_id=uuid4(),
        project_id=uuid4(),
        report_id=uuid4(),
        title="Research",
        status="running",
        active_job_id=uuid4(),
        next_sequence=5,
        revision=3,
        last_message_at=now,
        last_error_code=None,
        next_event_sequence=12,
        next_checkpoint_sequence=2,
        context_summary_through_sequence=1,
        compaction_count=1,
        last_checkpoint_at=now,
        created_at=now,
        updated_at=now,
    )
    assert session.next_event_sequence == 12
    assert session.next_checkpoint_sequence == 2
    assert session.compaction_count == 1
