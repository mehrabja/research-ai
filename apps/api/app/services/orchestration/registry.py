"""M35 — Tool registry.

Only tools in this registry can be invoked by the orchestrator.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import OrchestrationUnknownTool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    key: str
    version: str
    description: str
    permission: str
    deterministic: bool
    timeout_seconds: int
    max_attempts: int
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    idempotent: bool


ToolFn = Callable[[Session, "ToolContext"], dict[str, Any]]


@dataclass
class ToolContext:
    project_id: uuid.UUID
    report_id: uuid.UUID
    user_id: uuid.UUID | None
    run_id: uuid.UUID
    node_id: uuid.UUID
    payload: dict[str, Any]


_TOOLS: dict[str, tuple[ToolSpec, ToolFn]] = {}


def register_tool(spec: ToolSpec, fn: ToolFn) -> None:
    _TOOLS[spec.key] = (spec, fn)


def get_tool(key: str) -> tuple[ToolSpec, ToolFn]:
    entry = _TOOLS.get(key)
    if entry is None:
        raise OrchestrationUnknownTool(key)
    return entry


def list_tools() -> list[str]:
    return sorted(_TOOLS.keys())


def tool_exists(key: str) -> bool:
    return key in _TOOLS


# Late import to trigger registration in tools.py.
# This must be at the very bottom of the module to avoid a circular
# import error (tools.py imports from this module at load time).
from app.services.orchestration import tools as _tools  # noqa: E402,F401

__all__ = [
    "ToolSpec",
    "ToolContext",
    "ToolFn",
    "register_tool",
    "get_tool",
    "list_tools",
    "tool_exists",
]
