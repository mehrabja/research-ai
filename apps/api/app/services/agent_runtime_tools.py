"""Approval-gated access to the existing orchestration ToolSpec registry."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.services.orchestration.registry import ToolSpec, get_tool

# Registry additions are not automatically model-callable. Non-idempotent
# tools are excluded so worker recovery cannot silently repeat uncertain effects.
AGENT_TOOL_ALLOWLIST = frozenset(
    {
        "build_plan",
        "manuscript_generate",
        "technical_intelligence",
        "generate_citations",
        "academic_qa",
        "humanize",
        "manuscript_prose_generate",
        "target_compliance",
    }
)
_TOOL_CALL_FIELDS = frozenset({"type", "tool", "arguments", "reason"})
_TOOL_CALL_MARKER = re.compile(r'"type"\s*:\s*"tool_call"')


def get_agent_tool_spec(key: str) -> ToolSpec:
    if key not in AGENT_TOOL_ALLOWLIST:
        raise ValueError("requested tool is not available to Agent Runtime")
    spec, _fn = get_tool(key)
    if spec.permission not in {"read", "write"} or not spec.idempotent:
        raise ValueError("tool is not safe for Agent Runtime execution")
    return spec


def available_agent_tools(*, project_bound: bool = True) -> list[dict[str, Any]]:
    if not project_bound:
        return []
    catalog: list[dict[str, Any]] = []
    for key in sorted(AGENT_TOOL_ALLOWLIST):
        try:
            spec = get_agent_tool_spec(key)
        except Exception:
            continue
        catalog.append(
            {
                "name": spec.key,
                "description": spec.description[:500],
                "arguments_schema": spec.input_schema,
                "permission": spec.permission,
                "approval_required": True,
            }
        )
    return catalog


def _validate_schema_value(schema: dict[str, Any], value: Any, path: str) -> None:
    expected = schema.get("type")
    expected_types = expected if isinstance(expected, list) else [expected]
    expected_types = [item for item in expected_types if item is not None]

    if expected_types:
        def matches(type_name: str) -> bool:
            if type_name == "object":
                return isinstance(value, dict)
            if type_name == "array":
                return isinstance(value, list)
            if type_name == "string":
                return isinstance(value, str)
            if type_name == "boolean":
                return isinstance(value, bool)
            if type_name == "integer":
                return isinstance(value, int) and not isinstance(value, bool)
            if type_name == "number":
                return isinstance(value, (int, float)) and not isinstance(value, bool)
            if type_name == "null":
                return value is None
            return False

        if not any(matches(type_name) for type_name in expected_types):
            raise ValueError(f"invalid type for tool argument {path}")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"invalid value for tool argument {path}")

    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            raise ValueError(f"tool argument {path} is too short")
        if len(value) > int(schema.get("maxLength", 20000)):
            raise ValueError(f"tool argument {path} is too long")
        if schema.get("format") == "uuid":
            try:
                uuid.UUID(value)
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"tool argument {path} must be a UUID") from exc

    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            raise ValueError(f"tool argument {path} has too few items")
        if len(value) > int(schema.get("maxItems", 100)):
            raise ValueError(f"tool argument {path} has too many items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_schema_value(item_schema, item, f"{path}[{index}]")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError("tool input schema is invalid")
        unknown = set(value).difference(properties)
        if unknown:
            raise ValueError(
                "unsupported tool argument(s): " + ", ".join(sorted(unknown)[:8])
            )
        missing = set(schema.get("required", [])).difference(value)
        if missing:
            raise ValueError(
                "missing tool argument(s): " + ", ".join(sorted(missing)[:8])
            )
        for key, item in value.items():
            child_schema = properties.get(key)
            if not isinstance(child_schema, dict):
                raise ValueError(f"tool argument schema is missing for {key}")
            _validate_schema_value(child_schema, item, f"{path}.{key}")


def validate_agent_tool_arguments(
    spec: ToolSpec, arguments: dict[str, Any]
) -> dict[str, Any]:
    if spec.key not in AGENT_TOOL_ALLOWLIST:
        raise ValueError("requested tool is not available to Agent Runtime")
    if spec.permission not in {"read", "write"} or not spec.idempotent:
        raise ValueError("tool is not safe for Agent Runtime execution")
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be a JSON object")
    schema = spec.input_schema
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError("tool input schema is not a supported object schema")
    _validate_schema_value(schema, arguments, "arguments")
    return json.loads(json.dumps(arguments, ensure_ascii=False, allow_nan=False))


def parse_agent_tool_request(response_text: str) -> dict[str, Any] | None:
    """Recognize one strict JSON tool request; ordinary prose remains prose."""
    try:
        payload = json.loads(response_text.strip())
    except (json.JSONDecodeError, TypeError):
        if isinstance(response_text, str) and _TOOL_CALL_MARKER.search(response_text):
            raise ValueError("model returned a malformed tool-call envelope")
        return None

    if not isinstance(payload, dict) or payload.get("type") != "tool_call":
        return None
    if set(payload) != _TOOL_CALL_FIELDS:
        raise ValueError("tool-call envelope contains unsupported fields")

    key = payload.get("tool")
    reason = payload.get("reason")
    arguments = payload.get("arguments")
    if not isinstance(key, str):
        raise ValueError("tool-call name must be a string")
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
        raise ValueError("tool-call reason must contain 1 to 500 characters")

    spec = get_agent_tool_spec(key)
    clean_arguments = validate_agent_tool_arguments(spec, arguments)
    return {
        "spec": spec,
        "tool_key": spec.key,
        "tool_version": spec.version,
        "tool_description": spec.description[:500],
        "arguments": clean_arguments,
        "reason": reason.strip(),
    }


__all__ = [
    "AGENT_TOOL_ALLOWLIST",
    "available_agent_tools",
    "get_agent_tool_spec",
    "parse_agent_tool_request",
    "validate_agent_tool_arguments",
]
