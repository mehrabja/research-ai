from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

import app.api.routes.mcp_connections as mcp_routes
from app.db.models.membership import WorkspaceMembership
from app.db.models.mcp_connection import WorkspaceMCPConnection
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.session import SessionLocal
from app.main import app
from app.services.mcp_registry import MCPServerProfile
from tests._m37_cleanup import purge_test_users

client = TestClient(app)

def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

def _register(cleanup_users: list[uuid.UUID]) -> tuple[uuid.UUID, str]:
    email = f"mcp-{uuid.uuid4().hex[:12]}@example.com"
    password = "Correct Horse Battery Staple!"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    user_id = uuid.UUID(response.json()["id"])
    cleanup_users.append(user_id)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    return user_id, login.json()["access_token"]

@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        project_ids = select(Project.id).where(Project.user_id.in_(user_ids))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(project_ids))
        )
        db.execute(delete(Report).where(Report.user_id.in_(user_ids)))
        db.execute(delete(Project).where(Project.user_id.in_(user_ids)))
        purge_test_users(db, user_ids)
        db.commit()

def _configured_profile() -> MCPServerProfile:
    return MCPServerProfile(
        key="kegg",
        display_name="KEGG MCP",
        description="Configured KEGG connector",
        endpoint_url="https://mcp.example.org/mcp",
        hostname="mcp.example.org",
        auth_secret_ref="MCP_KEGG_TOKEN",
    )

def test_workspace_mcp_profiles_hide_endpoint_and_secret_reference(
    cleanup_users, monkeypatch
) -> None:
    _user_id, token = _register(cleanup_users)
    workspace = client.post(
        "/api/v1/workspaces",
        headers=_auth(token),
        json={"name": "MCP workspace"},
    )
    assert workspace.status_code == 201, workspace.text
    workspace_id = workspace.json()["id"]

    profile = _configured_profile()
    monkeypatch.setattr(mcp_routes, "list_mcp_server_profiles", lambda: [profile])

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/mcp-server-profiles",
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "profile_key": "kegg",
            "display_name": "KEGG MCP",
            "description": "Configured KEGG connector",
            "authentication_required": True,
            "transport": "streamable_http",
        }
    ]
    assert "endpoint_url" not in response.text
    assert "auth_secret_ref" not in response.text
    assert "MCP_KEGG_TOKEN" not in response.text

def test_mcp_connection_create_is_admin_only_and_workspace_scoped(
    cleanup_users, monkeypatch
) -> None:
    _, owner_token = _register(cleanup_users)
    member_id, member_token = _register(cleanup_users)
    _, outsider_token = _register(cleanup_users)

    workspace = client.post(
        "/api/v1/workspaces",
        headers=_auth(owner_token),
        json={"name": "Shared MCP workspace"},
    )
    assert workspace.status_code == 201, workspace.text
    workspace_id = uuid.UUID(workspace.json()["id"])

    with SessionLocal() as db:
        db.add(
            WorkspaceMembership(
                workspace_id=workspace_id,
                user_id=member_id,
                role="member",
                status="active",
            )
        )
        db.commit()

    profile = _configured_profile()
    monkeypatch.setattr(mcp_routes, "get_mcp_server_profile", lambda key: profile)

    forbidden = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections",
        headers=_auth(member_token),
        json={"profile_key": "kegg"},
    )
    assert forbidden.status_code == 403

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections",
        headers=_auth(owner_token),
        json={"profile_key": "kegg"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["profile_key"] == "kegg"
    assert created.json()["status"] == "enabled"
    assert created.json()["discovery_status"] == "never"
    assert "endpoint_url" not in created.text
    assert "auth_secret_ref" not in created.text
    assert "MCP_KEGG_TOKEN" not in created.text

    outsider = client.get(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections",
        headers=_auth(outsider_token),
    )
    assert outsider.status_code == 404

def test_reenabling_an_already_enabled_connection_preserves_snapshot(
    cleanup_users, monkeypatch
) -> None:
    _user_id, token = _register(cleanup_users)
    workspace = client.post(
        "/api/v1/workspaces",
        headers=_auth(token),
        json={"name": "MCP idempotency workspace"},
    )
    workspace_id = workspace.json()["id"]
    profile = _configured_profile()
    monkeypatch.setattr(mcp_routes, "get_mcp_server_profile", lambda key: profile)

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections",
        headers=_auth(token),
        json={"profile_key": "kegg"},
    )
    assert created.status_code == 201, created.text
    connection_id = uuid.UUID(created.json()["id"])

    with SessionLocal() as db:
        row = db.get(WorkspaceMCPConnection, connection_id)
        assert row is not None
        row.discovery_status = "success"
        row.tool_count = 1
        row.capability_snapshot = {"tools": [{"name": "search", "executable": False}]}
        db.commit()

    repeated = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections",
        headers=_auth(token),
        json={"profile_key": "kegg"},
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["discovery_status"] == "success"
    assert repeated.json()["tool_count"] == 1
    assert repeated.json()["capability_snapshot"]["tools"][0]["executable"] is False

def test_mcp_discovery_is_read_only_and_persists_bounded_inert_snapshot(
    cleanup_users, monkeypatch
) -> None:
    _user_id, token = _register(cleanup_users)
    workspace = client.post(
        "/api/v1/workspaces",
        headers=_auth(token),
        json={"name": "MCP discovery workspace"},
    )
    workspace_id = workspace.json()["id"]
    profile = _configured_profile()
    monkeypatch.setattr(mcp_routes, "get_mcp_server_profile", lambda key: profile)

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections",
        headers=_auth(token),
        json={"profile_key": "kegg"},
    )
    assert created.status_code == 201, created.text
    connection_id = created.json()["id"]

    async def fake_discovery(_profile_key: str) -> dict:
        return {
            "protocol_version": "2026-07-28",
            "server": {"name": "Test MCP", "version": "1.0"},
            "tools": [
                {
                    "name": "search_records",
                    "input_schema": {"type": "object"},
                    "requires_approval": True,
                    "executable": False,
                    "source_trust": "untrusted_remote",
                }
            ],
            "resources": [],
            "resource_templates": [],
            "prompts": [],
        }

    monkeypatch.setattr(mcp_routes, "discover_mcp_server", fake_discovery)
    discovered = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections/{connection_id}/discover",
        headers=_auth(token),
    )
    assert discovered.status_code == 200, discovered.text
    body = discovered.json()
    assert body["tools_discovered"] == 1
    assert body["executable_tools_added"] == 0
    assert body["connection"]["discovery_status"] == "success"
    assert body["connection"]["capability_snapshot"]["tools"][0]["executable"] is False
    assert body["connection"]["capability_snapshot"]["tools"][0]["requires_approval"] is True

def test_mcp_discovery_failure_is_redacted_from_api_response(
    cleanup_users, monkeypatch
) -> None:
    _user_id, token = _register(cleanup_users)
    workspace = client.post(
        "/api/v1/workspaces",
        headers=_auth(token),
        json={"name": "MCP failure workspace"},
    )
    workspace_id = workspace.json()["id"]
    profile = _configured_profile()
    monkeypatch.setattr(mcp_routes, "get_mcp_server_profile", lambda key: profile)

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections",
        headers=_auth(token),
        json={"profile_key": "kegg"},
    )
    connection_id = created.json()["id"]

    async def fail_discovery(_profile_key: str) -> dict:
        raise mcp_routes.MCPRemoteConnectionError("upstream secret must not leak")

    monkeypatch.setattr(mcp_routes, "discover_mcp_server", fail_discovery)
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections/{connection_id}/discover",
        headers=_auth(token),
    )
    assert response.status_code == 502
    assert "upstream secret must not leak" not in response.text
    listed = client.get(
        f"/api/v1/workspaces/{workspace_id}/mcp-connections",
        headers=_auth(token),
    )
    assert listed.status_code == 200
    assert listed.json()[0]["discovery_status"] == "failed"
    assert listed.json()[0]["last_error_code"] == "MCP_DISCOVERY_FAILED"
