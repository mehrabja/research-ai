"""M35 — Node execution via registered tools only."""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import (
    OrchestrationUnknownTool,
)
from app.services.orchestration.registry import (
    ToolContext,
    get_tool,
)


def execute_node(
    db: Session,
    *,
    node_key: str,
    project_id,
    report_id,
    user_id,
    run_id,
    node_id,
    payload: dict,
) -> dict[str, Any]:
    """Execute a single orchestration node via its registered tool.

    The only allowable operations are those registered in the tool
    registry. No arbitrary code, no SQL, no shell.
    """
    try:
        spec, fn = get_tool(node_key)
    except OrchestrationUnknownTool:
        raise
    _ = spec
    ctx = ToolContext(
        project_id=project_id,
        report_id=report_id,
        user_id=user_id,
        run_id=run_id,
        node_id=node_id,
        payload=payload,
    )
    started = time.perf_counter()
    out = fn(db, ctx)
    out.setdefault(
        "_duration_ms",
        int((time.perf_counter() - started) * 1000),
    )
    return out


__all__ = ["execute_node"]
