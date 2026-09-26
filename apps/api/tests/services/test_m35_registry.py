"""M35 — tool registry tests."""
from __future__ import annotations

import pytest

from app.core.exceptions import OrchestrationUnknownTool
from app.services.orchestration.registry import (
    get_tool,
    list_tools,
    tool_exists,
)


def test_registry_has_required_tools() -> None:
    keys = list_tools()
    for key in (
        "build_plan",
        "technical_intelligence",
        "generate_citations",
        "academic_qa",
        "humanize",
        "target_compliance",
    ):
        assert key in keys


def test_unknown_tool_rejected() -> None:
    with pytest.raises(OrchestrationUnknownTool):
        get_tool("not_a_real_tool")


def test_tool_exists() -> None:
    assert tool_exists("academic_qa")
    assert not tool_exists("nope")


def test_tool_specs_are_sane() -> None:
    for key in list_tools():
        spec, _fn = get_tool(key)
        assert spec.key == key
        assert spec.version
        assert spec.timeout_seconds > 0
        assert spec.max_attempts >= 1
        assert spec.permission in ("read", "write", "manage")
