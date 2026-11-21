from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.mcp_client import (
    MCPRemoteConnectionError,
    build_capability_snapshot,
)

def test_discovered_tool_metadata_is_always_inert_and_marked_untrusted() -> None:
    snapshot = build_capability_snapshot(
        protocol_version="2026-07-28",
        server_info=SimpleNamespace(name="Scientific MCP", version="1.0"),
        tools=[
            SimpleNamespace(
                name="search",
                title="Search",
                description="Find relevant records.",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            )
        ],
        resources=[SimpleNamespace(uri="resource://records", name="records")],
        resource_templates=[],
        prompts=[SimpleNamespace(name="review", arguments=[])],
    )

    assert snapshot["protocol_version"] == "2026-07-28"
    assert snapshot["tools"][0]["requires_approval"] is True
    assert snapshot["tools"][0]["executable"] is False
    assert snapshot["tools"][0]["source_trust"] == "untrusted_remote"
    assert snapshot["resources"][0]["source_trust"] == "untrusted_remote"
    assert snapshot["prompts"][0]["source_trust"] == "untrusted_remote"

def test_discovery_rejects_invalid_tool_schema() -> None:
    with pytest.raises(MCPRemoteConnectionError):
        build_capability_snapshot(
            protocol_version="2026-07-28",
            server_info=None,
            tools=[
                SimpleNamespace(
                    name="unsafe",
                    title=None,
                    description=None,
                    input_schema=["not", "an", "object"],
                )
            ],
            resources=[],
            resource_templates=[],
            prompts=[],
        )

def test_discovery_rejects_tool_schema_with_non_object_root() -> None:
    with pytest.raises(MCPRemoteConnectionError):
        build_capability_snapshot(
            protocol_version="2026-07-28",
            server_info=None,
            tools=[
                SimpleNamespace(
                    name="unsafe",
                    title=None,
                    description=None,
                    input_schema={"type": "string"},
                )
            ],
            resources=[],
            resource_templates=[],
            prompts=[],
        )

def test_discovery_rejects_control_characters_in_remote_tool_name() -> None:
    with pytest.raises(MCPRemoteConnectionError):
        build_capability_snapshot(
            protocol_version="2026-07-28",
            server_info=None,
            tools=[
                SimpleNamespace(
                    name="do\nnot-trust",
                    title=None,
                    description=None,
                    input_schema={"type": "object"},
                )
            ],
            resources=[],
            resource_templates=[],
            prompts=[],
        )

def test_discovery_rejects_duplicate_tool_names() -> None:
    tool = SimpleNamespace(
        name="search",
        title=None,
        description=None,
        input_schema={"type": "object"},
    )
    with pytest.raises(MCPRemoteConnectionError, match="duplicate tool names"):
        build_capability_snapshot(
            protocol_version="2026-07-28",
            server_info=None,
            tools=[tool, tool],
            resources=[],
            resource_templates=[],
            prompts=[],
        )
