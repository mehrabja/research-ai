from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.agent_runtime import (
    AgentRuntimeMessageCreate,
    AgentRuntimeSessionCreate,
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
