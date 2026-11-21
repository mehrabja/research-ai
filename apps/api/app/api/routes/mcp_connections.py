"""Workspace-scoped MCP profile registrations and read-only discovery."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.rate_limit_deps import enforce_user_rate_limit
from app.core.exceptions import AppError, InsufficientRole
from app.db.models.mcp_connection import WorkspaceMCPConnection
from app.db.models.user import User
from app.db.session import get_db
from app.domain.membership import ROLE_ADMIN, role_at_least
from app.schemas.mcp_connection import (
    MCPConnectionCreate,
    MCPConnectionRead,
    MCPDiscoverySummary,
    MCPServerProfileRead,
)
from app.services import workspaces as workspaces_service
from app.services.audit import emit_audit
from app.services.mcp_client import MCPRemoteConnectionError, discover_mcp_server
from app.services.mcp_registry import (
    MCPProfileConfigurationError,
    MCPProfileNotFoundError,
    get_mcp_server_profile,
    list_mcp_server_profiles,
)

router = APIRouter(prefix="/workspaces", tags=["mcp-connections"])

class MCPServerConfigurationUnavailable(AppError):
    code = "MCP_SERVER_CONFIGURATION_UNAVAILABLE"
    status_code = 503
    message = "MCP server profiles are not configured correctly."

class MCPServerProfileNotFound(AppError):
    code = "MCP_SERVER_PROFILE_NOT_FOUND"
    status_code = 404
    message = "MCP server profile is not configured."

class MCPConnectionNotFound(AppError):
    code = "MCP_CONNECTION_NOT_FOUND"
    status_code = 404
    message = "MCP connection was not found."

class MCPDiscoveryFailed(AppError):
    code = "MCP_DISCOVERY_FAILED"
    status_code = 502
    message = "MCP server discovery failed."

def _profiles():
    try:
        return list_mcp_server_profiles()
    except MCPProfileConfigurationError as exc:
        raise MCPServerConfigurationUnavailable() from exc

def _profile_or_404(profile_key: str):
    try:
        return get_mcp_server_profile(profile_key)
    except MCPProfileConfigurationError as exc:
        raise MCPServerConfigurationUnavailable() from exc
    except MCPProfileNotFoundError as exc:
        raise MCPServerProfileNotFound() from exc

def _require_workspace_member(
    db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID
):
    return workspaces_service.get_workspace_for_user(
        db, workspace_id=workspace_id, user_id=user_id
    )

def _require_workspace_admin(
    db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID
):
    workspace, role = _require_workspace_member(
        db, workspace_id=workspace_id, user_id=user_id
    )
    if workspace.status != "active" or not role_at_least(role, ROLE_ADMIN):
        raise InsufficientRole()
    return workspace

def _read_connection(row: WorkspaceMCPConnection) -> MCPConnectionRead:
    try:
        profile_name = get_mcp_server_profile(row.profile_key).display_name
    except (MCPProfileConfigurationError, MCPProfileNotFoundError):
        profile_name = row.profile_key
    return MCPConnectionRead(
        id=row.id,
        workspace_id=row.workspace_id,
        profile_key=row.profile_key,
        profile_name=profile_name,
        status=row.status,
        discovery_status=row.discovery_status,
        protocol_version=row.protocol_version,
        server_name=row.server_name,
        server_version=row.server_version,
        tool_count=row.tool_count,
        resource_count=row.resource_count,
        resource_template_count=row.resource_template_count,
        prompt_count=row.prompt_count,
        capability_snapshot=dict(row.capability_snapshot or {}),
        last_discovered_at=row.last_discovered_at,
        last_error_code=row.last_error_code,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

@router.get(
    "/{workspace_id}/mcp-server-profiles",
    response_model=list[MCPServerProfileRead],
)
def list_workspace_mcp_profiles(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MCPServerProfileRead]:
    _require_workspace_member(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    return [
        MCPServerProfileRead(
            profile_key=profile.key,
            display_name=profile.display_name,
            description=profile.description,
            authentication_required=profile.authentication_required,
        )
        for profile in _profiles()
    ]

@router.get(
    "/{workspace_id}/mcp-connections",
    response_model=list[MCPConnectionRead],
)
def list_workspace_mcp_connections(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MCPConnectionRead]:
    _require_workspace_member(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    rows = db.execute(
        select(WorkspaceMCPConnection)
        .where(WorkspaceMCPConnection.workspace_id == workspace_id)
        .order_by(WorkspaceMCPConnection.created_at.asc(), WorkspaceMCPConnection.id.asc())
    ).scalars().all()
    return [_read_connection(row) for row in rows]

@router.post(
    "/{workspace_id}/mcp-connections",
    response_model=MCPConnectionRead,
    status_code=status.HTTP_201_CREATED,
)
def enable_workspace_mcp_connection(
    workspace_id: uuid.UUID,
    body: MCPConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MCPConnectionRead:
    _require_workspace_admin(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    profile = _profile_or_404(body.profile_key)
    # Serialize concurrent create/reactivate requests, including when no row exists yet.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"m42:mcp:{workspace_id}:{profile.key}"},
    )
    row = db.execute(
        select(WorkspaceMCPConnection)
        .where(
            WorkspaceMCPConnection.workspace_id == workspace_id,
            WorkspaceMCPConnection.profile_key == profile.key,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = WorkspaceMCPConnection(
            workspace_id=workspace_id,
            profile_key=profile.key,
            created_by_user_id=current_user.id,
        )
        db.add(row)
    elif row.status == "disabled":
        row.status = "enabled"
        row.discovery_status = "never"
        row.protocol_version = None
        row.server_name = None
        row.server_version = None
        row.tool_count = 0
        row.resource_count = 0
        row.resource_template_count = 0
        row.prompt_count = 0
        row.capability_snapshot = {}
        row.last_discovered_at = None
        row.last_error_code = None
    db.commit()
    db.refresh(row)
    emit_audit(
        "MCP_CONNECTION_ENABLED",
        user_id=str(current_user.id),
        workspace_id=str(workspace_id),
        reason=profile.key,
        outcome="success",
    )
    return _read_connection(row)

@router.delete(
    "/{workspace_id}/mcp-connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def disable_workspace_mcp_connection(
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    _require_workspace_admin(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    row = db.execute(
        select(WorkspaceMCPConnection)
        .where(
            WorkspaceMCPConnection.id == connection_id,
            WorkspaceMCPConnection.workspace_id == workspace_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise MCPConnectionNotFound()
    row.status = "disabled"
    db.commit()
    emit_audit(
        "MCP_CONNECTION_DISABLED",
        user_id=str(current_user.id),
        workspace_id=str(workspace_id),
        reason=row.profile_key,
        outcome="success",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post(
    "/{workspace_id}/mcp-connections/{connection_id}/discover",
    response_model=MCPDiscoverySummary,
    dependencies=[
        Depends(
            enforce_user_rate_limit(
                "mcp_discovery",
                setting_name="mcp_discovery_rate_limit_per_minute",
            )
        )
    ],
)
async def discover_workspace_mcp_connection(
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MCPDiscoverySummary:
    _require_workspace_admin(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    row = db.execute(
        select(WorkspaceMCPConnection)
        .where(
            WorkspaceMCPConnection.id == connection_id,
            WorkspaceMCPConnection.workspace_id == workspace_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise MCPConnectionNotFound()
    if row.status != "enabled":
        raise AppError(
            "MCP connection is disabled",
            code="MCP_CONNECTION_DISABLED",
        )

    # Release the transaction and row lock before remote network I/O.
    profile_key = row.profile_key
    db.commit()

    try:
        snapshot = await discover_mcp_server(profile_key)
    except (
        MCPProfileConfigurationError,
        MCPProfileNotFoundError,
        MCPRemoteConnectionError,
    ) as exc:
        failed_row = db.execute(
            select(WorkspaceMCPConnection)
            .where(
                WorkspaceMCPConnection.id == connection_id,
                WorkspaceMCPConnection.workspace_id == workspace_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if failed_row is not None and failed_row.status == "enabled":
            failed_row.discovery_status = "failed"
            failed_row.last_error_code = "MCP_DISCOVERY_FAILED"
            db.commit()
        else:
            db.rollback()
        emit_audit(
            "MCP_CONNECTION_DISCOVERY_FAILED",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            reason=profile_key,
            outcome="failed",
        )
        raise MCPDiscoveryFailed() from exc

    row = db.execute(
        select(WorkspaceMCPConnection)
        .where(
            WorkspaceMCPConnection.id == connection_id,
            WorkspaceMCPConnection.workspace_id == workspace_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise MCPConnectionNotFound()
    if row.status != "enabled":
        db.rollback()
        raise AppError(
            "MCP connection was disabled while discovery was running",
            code="MCP_CONNECTION_DISABLED",
        )

    server = snapshot.get("server", {})
    row.discovery_status = "success"
    row.protocol_version = str(snapshot.get("protocol_version") or "")[:40] or None
    row.server_name = str(server.get("name") or "")[:120] or None
    row.server_version = str(server.get("version") or "")[:80] or None
    row.tool_count = len(snapshot.get("tools", []))
    row.resource_count = len(snapshot.get("resources", []))
    row.resource_template_count = len(snapshot.get("resource_templates", []))
    row.prompt_count = len(snapshot.get("prompts", []))
    row.capability_snapshot = snapshot
    row.last_discovered_at = datetime.now(UTC)
    row.last_error_code = None
    db.commit()
    db.refresh(row)
    emit_audit(
        "MCP_CONNECTION_DISCOVERED",
        user_id=str(current_user.id),
        workspace_id=str(workspace_id),
        reason=profile_key,
        outcome="success",
        quantity=row.tool_count,
        metric="mcp.tools",
    )
    return MCPDiscoverySummary(
        connection=_read_connection(row),
        tools_discovered=row.tool_count,
        resources_discovered=row.resource_count,
        prompts_discovered=row.prompt_count,
    )
