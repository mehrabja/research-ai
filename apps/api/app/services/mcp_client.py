"""Bounded, read-only MCP discovery over the official Streamable HTTP client."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

import anyio
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.core.config import get_settings
from app.core.secrets import get_secret_resolver
from app.services.mcp_registry import (
    MCPProfileConfigurationError,
    get_mcp_server_profile,
    validate_mcp_profile_destination,
)

_SAFE_NAME = re.compile(r"^[^\x00-\x1f\x7f]{1,128}$")
_MAX_DESCRIPTION_CHARS = 1200
_MAX_SCHEMA_BYTES = 24 * 1024
_MAX_SNAPSHOT_BYTES = 256 * 1024

class MCPRemoteConnectionError(RuntimeError):
    """A configured remote MCP server could not be reached or inspected."""

def _clean_text(value: object, *, limit: int = _MAX_DESCRIPTION_CHARS) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = "".join(char for char in value if char >= " " and char != "\x7f")
    return cleaned[:limit]

def _safe_name(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise MCPRemoteConnectionError(f"Remote MCP {label} name is invalid")
    name = _clean_text(value, limit=128)
    if not _SAFE_NAME.fullmatch(name):
        raise MCPRemoteConnectionError(f"Remote MCP {label} name is invalid")
    return name

def _json_object(value: object, *, label: str, max_bytes: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MCPRemoteConnectionError(f"Remote MCP {label} must be a JSON object")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        clean = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MCPRemoteConnectionError(f"Remote MCP {label} is not valid JSON") from exc
    if len(encoded.encode("utf-8")) > max_bytes:
        raise MCPRemoteConnectionError(f"Remote MCP {label} exceeds the metadata size limit")
    return clean

def build_capability_snapshot(
    *,
    protocol_version: str,
    server_info: object,
    tools: list[object],
    resources: list[object],
    resource_templates: list[object],
    prompts: list[object],
) -> dict[str, Any]:
    """Convert remote metadata into a bounded inert snapshot.

    Remote tool schemas and descriptions are untrusted data. The snapshot does
    not make any discovered tool executable or add it to the host tool registry.
    """
    server_name = _clean_text(getattr(server_info, "name", None), limit=120)
    server_version = _clean_text(getattr(server_info, "version", None), limit=80)

    normalized_tools: list[dict[str, Any]] = []
    for tool in tools:
        schema = _json_object(
            getattr(tool, "input_schema", None),
            label="tool input schema",
            max_bytes=_MAX_SCHEMA_BYTES,
        )
        if schema.get("type") != "object":
            raise MCPRemoteConnectionError("Remote MCP tool schema must have object root type")
        normalized_tools.append(
            {
                "name": _safe_name(getattr(tool, "name", None), label="tool"),
                "title": _clean_text(getattr(tool, "title", None), limit=160),
                "description": _clean_text(getattr(tool, "description", None)),
                "input_schema": schema,
                "requires_approval": True,
                "executable": False,
                "source_trust": "untrusted_remote",
            }
        )

    tool_names = [item["name"] for item in normalized_tools]
    if len(tool_names) != len(set(tool_names)):
        raise MCPRemoteConnectionError("Remote MCP returned duplicate tool names")

    normalized_resources: list[dict[str, Any]] = []
    for resource in resources:
        normalized_resources.append(
            {
                "uri": _clean_text(str(getattr(resource, "uri", "")), limit=2048),
                "name": _clean_text(getattr(resource, "name", None), limit=160),
                "title": _clean_text(getattr(resource, "title", None), limit=160),
                "description": _clean_text(getattr(resource, "description", None)),
                "mime_type": _clean_text(getattr(resource, "mime_type", None), limit=120),
                "source_trust": "untrusted_remote",
            }
        )

    normalized_templates: list[dict[str, Any]] = []
    for template in resource_templates:
        normalized_templates.append(
            {
                "uri_template": _clean_text(
                    str(getattr(template, "uri_template", "")), limit=2048
                ),
                "name": _clean_text(getattr(template, "name", None), limit=160),
                "title": _clean_text(getattr(template, "title", None), limit=160),
                "description": _clean_text(getattr(template, "description", None)),
                "mime_type": _clean_text(getattr(template, "mime_type", None), limit=120),
                "source_trust": "untrusted_remote",
            }
        )

    resource_uris = [item["uri"] for item in normalized_resources]
    if len(resource_uris) != len(set(resource_uris)):
        raise MCPRemoteConnectionError("Remote MCP returned duplicate resource URIs")

    normalized_prompts: list[dict[str, Any]] = []
    for prompt in prompts:
        arguments = []
        for argument in getattr(prompt, "arguments", None) or []:
            arguments.append(
                {
                    "name": _safe_name(getattr(argument, "name", None), label="prompt argument"),
                    "description": _clean_text(getattr(argument, "description", None)),
                    "required": bool(getattr(argument, "required", False)),
                }
            )
        normalized_prompts.append(
            {
                "name": _safe_name(getattr(prompt, "name", None), label="prompt"),
                "title": _clean_text(getattr(prompt, "title", None), limit=160),
                "description": _clean_text(getattr(prompt, "description", None)),
                "arguments": arguments,
                "source_trust": "untrusted_remote",
            }
        )

    prompt_names = [item["name"] for item in normalized_prompts]
    if len(prompt_names) != len(set(prompt_names)):
        raise MCPRemoteConnectionError("Remote MCP returned duplicate prompt names")

    snapshot = {
        "protocol_version": _clean_text(protocol_version, limit=40),
        "server": {"name": server_name, "version": server_version},
        "tools": normalized_tools,
        "resources": normalized_resources,
        "resource_templates": normalized_templates,
        "prompts": normalized_prompts,
    }
    _json_object(snapshot, label="capability snapshot", max_bytes=_MAX_SNAPSHOT_BYTES)
    return snapshot

async def _collect_pages(
    fetch_page: Callable[..., Any],
    *,
    collection_name: str,
    max_items: int,
    max_pages: int = 10,
) -> list[object]:
    items: list[object] = []
    cursor: str | None = None
    for _ in range(max_pages):
        page = await fetch_page(cursor=cursor)
        page_items = getattr(page, collection_name, None)
        if not isinstance(page_items, list):
            raise MCPRemoteConnectionError("Remote MCP returned an invalid discovery page")
        items.extend(page_items)
        if len(items) > max_items:
            raise MCPRemoteConnectionError("Remote MCP discovery item limit exceeded")
        cursor = getattr(page, "next_cursor", None)
        if cursor is None:
            return items
    raise MCPRemoteConnectionError("Remote MCP discovery pagination limit exceeded")

async def _discover_with_client(client: Client) -> dict[str, Any]:
    settings = get_settings()
    max_items = settings.mcp_discovery_max_items
    tools = await _collect_pages(client.list_tools, collection_name="tools", max_items=max_items)
    resources = await _collect_pages(
        client.list_resources, collection_name="resources", max_items=max_items
    )
    templates = await _collect_pages(
        client.list_resource_templates,
        collection_name="resource_templates",
        max_items=max_items,
    )
    prompts = await _collect_pages(
        client.list_prompts, collection_name="prompts", max_items=max_items
    )
    return build_capability_snapshot(
        protocol_version=client.protocol_version,
        server_info=client.server_info,
        tools=tools,
        resources=resources,
        resource_templates=templates,
        prompts=prompts,
    )

async def discover_mcp_server(profile_key: str) -> dict[str, Any]:
    """Connect to one deployment-configured server and list bounded metadata only."""
    profile = get_mcp_server_profile(profile_key)
    settings = get_settings()
    timeout = httpx2.Timeout(
        connect=settings.mcp_connect_timeout_seconds,
        read=settings.mcp_read_timeout_seconds,
        write=settings.mcp_write_timeout_seconds,
        pool=settings.mcp_connect_timeout_seconds,
    )

    try:
        with anyio.fail_after(settings.mcp_discovery_timeout_seconds):
            # DNS resolution is bounded by the same discovery deadline.
            await anyio.to_thread.run_sync(
                validate_mcp_profile_destination,
                profile,
                abandon_on_cancel=True,
            )

            headers: dict[str, str] = {}
            if profile.auth_secret_ref:
                secret = get_secret_resolver().get_secret(profile.auth_secret_ref)
                if not secret or "\r" in secret or "\n" in secret:
                    raise MCPProfileConfigurationError(
                        "Configured MCP credential is unavailable"
                    )
                headers["Authorization"] = f"Bearer {secret}"

            async with httpx2.AsyncClient(
                headers=headers,
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
                verify=True,
                limits=httpx2.Limits(
                    max_connections=4,
                    max_keepalive_connections=2,
                ),
            ) as http_client:
                transport = streamable_http_client(
                    profile.endpoint_url,
                    http_client=http_client,
                    max_sse_event_size=256 * 1024,
                )
                async with Client(transport) as mcp_client:
                    return await _discover_with_client(mcp_client)
    except MCPProfileConfigurationError:
        raise
    except MCPRemoteConnectionError:
        raise
    except TimeoutError as exc:
        raise MCPRemoteConnectionError("MCP discovery timed out") from exc
    except Exception as exc:
        raise MCPRemoteConnectionError("MCP discovery request failed") from exc

__all__ = [
    "MCPRemoteConnectionError",
    "build_capability_snapshot",
    "discover_mcp_server",
]
