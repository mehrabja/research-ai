from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services import mcp_registry


def _settings(profiles: object):
    return SimpleNamespace(mcp_server_profiles_json=json.dumps(profiles))

def test_profile_parser_accepts_exact_deployment_allowlisted_https_host(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_registry,
        "get_settings",
        lambda: _settings(
            {
                "kegg": {
                    "display_name": "KEGG MCP",
                    "description": "Configured KEGG integration.",
                    "endpoint_url": "https://mcp.example.org/mcp",
                    "allowed_hosts": ["mcp.example.org"],
                    "auth_secret_ref": "MCP_KEGG_TOKEN",
                }
            }
        ),
    )

    profile = mcp_registry.get_mcp_server_profile("kegg")

    assert profile.key == "kegg"
    assert profile.hostname == "mcp.example.org"
    assert profile.authentication_required is True
    assert "MCP_KEGG_TOKEN" not in repr(profile)
    assert "https://mcp.example.org" not in repr(profile)

@pytest.mark.parametrize(
    "endpoint,allowlist",
    [
        ("http://mcp.example.org/mcp", ["mcp.example.org"]),
        ("https://mcp.example.org:8443/mcp", ["mcp.example.org"]),
        ("https://user:pass@mcp.example.org/mcp", ["mcp.example.org"]),
        ("https://mcp.example.org/mcp?token=leak", ["mcp.example.org"]),
        ("https://other.example.org/mcp", ["mcp.example.org"]),
        ("https://127.0.0.1/mcp", ["127.0.0.1"]),
    ],
)
def test_profile_parser_rejects_unsafe_endpoint_forms(
    monkeypatch, endpoint: str, allowlist: list[str]
) -> None:
    monkeypatch.setattr(
        mcp_registry,
        "get_settings",
        lambda: _settings(
            {
                "test": {
                    "display_name": "Test",
                    "endpoint_url": endpoint,
                    "allowed_hosts": allowlist,
                }
            }
        ),
    )

    with pytest.raises(mcp_registry.MCPProfileConfigurationError):
        mcp_registry.list_mcp_server_profiles()

def test_profile_parser_rejects_unknown_profile_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_registry,
        "get_settings",
        lambda: _settings(
            {
                "test": {
                    "display_name": "Test",
                    "endpoint_url": "https://mcp.example.org/mcp",
                    "allowed_hosts": ["mcp.example.org"],
                    "command": "sh",
                }
            }
        ),
    )

    with pytest.raises(mcp_registry.MCPProfileConfigurationError):
        mcp_registry.list_mcp_server_profiles()

def test_profile_parser_rejects_invalid_secret_reference(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_registry,
        "get_settings",
        lambda: _settings(
            {
                "test": {
                    "display_name": "Test",
                    "endpoint_url": "https://mcp.example.org/mcp",
                    "allowed_hosts": ["mcp.example.org"],
                    "auth_secret_ref": "../../.env",
                }
            }
        ),
    )

    with pytest.raises(mcp_registry.MCPProfileConfigurationError):
        mcp_registry.list_mcp_server_profiles()

def test_profile_list_is_empty_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_registry,
        "get_settings",
        lambda: SimpleNamespace(mcp_server_profiles_json=""),
    )
    assert mcp_registry.list_mcp_server_profiles() == []

def test_destination_check_rejects_private_dns_answers(monkeypatch) -> None:
    profile = mcp_registry.MCPServerProfile(
        key="test",
        display_name="Test",
        description="",
        endpoint_url="https://mcp.example.org/mcp",
        hostname="mcp.example.org",
    )
    monkeypatch.setattr(
        mcp_registry.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("10.0.0.10", 443)),
        ],
    )

    with pytest.raises(mcp_registry.MCPProfileConfigurationError):
        mcp_registry.validate_mcp_profile_destination(profile)

def test_profile_parser_rejects_numeric_hostname_shorthand(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_registry,
        "get_settings",
        lambda: _settings(
            {
                "test": {
                    "display_name": "Test",
                    "endpoint_url": "https://2130706433/mcp",
                    "allowed_hosts": ["2130706433"],
                }
            }
        ),
    )
    with pytest.raises(mcp_registry.MCPProfileConfigurationError):
        mcp_registry.list_mcp_server_profiles()

def test_profile_parser_rejects_localhost_suffix(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_registry,
        "get_settings",
        lambda: _settings(
            {
                "test": {
                    "display_name": "Test",
                    "endpoint_url": "https://service.localhost/mcp",
                    "allowed_hosts": ["service.localhost"],
                }
            }
        ),
    )
    with pytest.raises(mcp_registry.MCPProfileConfigurationError):
        mcp_registry.list_mcp_server_profiles()

def test_destination_check_rejects_mixed_public_and_private_dns(monkeypatch) -> None:
    profile = mcp_registry.MCPServerProfile(
        key="test",
        display_name="Test",
        description="",
        endpoint_url="https://mcp.example.org/mcp",
        hostname="mcp.example.org",
    )
    monkeypatch.setattr(
        mcp_registry.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ],
    )
    with pytest.raises(mcp_registry.MCPProfileConfigurationError):
        mcp_registry.validate_mcp_profile_destination(profile)
