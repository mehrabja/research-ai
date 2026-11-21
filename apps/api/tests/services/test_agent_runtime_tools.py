from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services import agent_runtime_tools


def _spec(*, idempotent: bool = True):
    return SimpleNamespace(
        key="generate_citations",
        version="m39-tools-v2",
        description="Generate citations.",
        permission="write",
        idempotent=idempotent,
        input_schema={
            "type": "object",
            "required": ["manuscript_version_id"],
            "properties": {
                "manuscript_version_id": {"type": "string", "format": "uuid"},
                "mode": {"type": "string", "enum": ["academic", "plain"]},
            },
        },
    )


def test_tool_arguments_validate_required_fields_and_uuid() -> None:
    clean = agent_runtime_tools.validate_agent_tool_arguments(
        _spec(),
        {"manuscript_version_id": "11111111-1111-4111-8111-111111111111"},
    )
    assert clean["manuscript_version_id"].startswith("11111111")


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"manuscript_version_id": "not-a-uuid"},
        {
            "manuscript_version_id": "11111111-1111-4111-8111-111111111111",
            "unknown": True,
        },
        {
            "manuscript_version_id": "11111111-1111-4111-8111-111111111111",
            "mode": "unsafe",
        },
    ],
)
def test_tool_arguments_reject_missing_invalid_or_unknown_values(arguments) -> None:
    with pytest.raises(ValueError):
        agent_runtime_tools.validate_agent_tool_arguments(_spec(), arguments)


def test_non_idempotent_tools_are_rejected_even_if_allowlisted(monkeypatch) -> None:
    spec = _spec(idempotent=False)
    monkeypatch.setattr(agent_runtime_tools, "get_tool", lambda key: (spec, lambda *_: {}))
    with pytest.raises(ValueError, match="not safe"):
        agent_runtime_tools.get_agent_tool_spec(spec.key)


def test_tool_call_parser_ignores_normal_prose() -> None:
    assert agent_runtime_tools.parse_agent_tool_request(
        "Here is the evidence-based answer."
    ) is None


def test_tool_call_parser_returns_only_a_valid_registered_call(monkeypatch) -> None:
    spec = _spec()
    monkeypatch.setattr(
        agent_runtime_tools,
        "get_agent_tool_spec",
        lambda key: spec if key == spec.key else (_ for _ in ()).throw(ValueError()),
    )
    request = {
        "type": "tool_call",
        "tool": "generate_citations",
        "arguments": {
            "manuscript_version_id": "11111111-1111-4111-8111-111111111111"
        },
        "reason": "Create citations for the current manuscript version.",
    }
    parsed = agent_runtime_tools.parse_agent_tool_request(json.dumps(request))
    assert parsed is not None
    assert parsed["tool_key"] == "generate_citations"
    assert parsed["arguments"] == request["arguments"]


def test_tool_call_parser_rejects_unapproved_envelope_fields() -> None:
    request = {
        "type": "tool_call",
        "tool": "generate_citations",
        "arguments": {},
        "reason": "Create citations.",
        "shell": "echo unsafe",
    }
    with pytest.raises(ValueError):
        agent_runtime_tools.parse_agent_tool_request(json.dumps(request))


def test_tool_call_parser_rejects_malformed_tool_call_json() -> None:
    with pytest.raises(ValueError):
        agent_runtime_tools.parse_agent_tool_request(
            '{"type":"tool_call","tool":"generate_citations"'
        )
