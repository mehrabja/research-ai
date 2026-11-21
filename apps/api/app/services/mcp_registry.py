"""Deployment-owned MCP server profiles.

Clients can select a configured profile key, never an endpoint URL or secret.
Secret references are resolved at runtime by the application's SecretResolver.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.core.config import get_settings

_PROFILE_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SECRET_REF = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")

class MCPProfileConfigurationError(ValueError):
    """The deployment-owned MCP profile configuration is invalid."""

class MCPProfileNotFoundError(LookupError):
    """The requested MCP server profile is not configured."""

@dataclass(frozen=True)
class MCPServerProfile:
    key: str
    display_name: str
    description: str
    endpoint_url: str = field(repr=False)
    hostname: str = field(repr=False)
    auth_secret_ref: str | None = field(default=None, repr=False)

    @property
    def authentication_required(self) -> bool:
        return self.auth_secret_ref is not None

def _normalize_hostname(value: str) -> str:
    try:
        normalized = value.rstrip(".").lower().encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise MCPProfileConfigurationError("MCP profile hostname is invalid") from exc
    if not normalized or len(normalized) > 253:
        raise MCPProfileConfigurationError("MCP profile hostname is invalid")
    # Reject numeric shorthand forms that some resolvers interpret as IP literals.
    if (
        re.fullmatch(r"[0-9.]+", normalized)
        or normalized == "localhost"
        or normalized.endswith((".localhost", ".local"))
    ):
        raise MCPProfileConfigurationError("MCP profiles must use public DNS hostnames")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise MCPProfileConfigurationError("MCP profiles must use DNS hostnames, not IP literals")
    if any(part == "" or len(part) > 63 for part in normalized.split(".")):
        raise MCPProfileConfigurationError("MCP profile hostname is invalid")
    return normalized

def _parse_profile(key: str, value: object) -> MCPServerProfile:
    if not isinstance(key, str) or not _PROFILE_KEY.fullmatch(key):
        raise MCPProfileConfigurationError("MCP profile key is invalid")
    if not isinstance(value, dict):
        raise MCPProfileConfigurationError("MCP profile entry must be an object")

    allowed_fields = {
        "display_name",
        "description",
        "endpoint_url",
        "allowed_hosts",
        "auth_secret_ref",
    }
    if set(value).difference(allowed_fields):
        raise MCPProfileConfigurationError("MCP profile contains unsupported fields")

    display_name = value.get("display_name")
    description = value.get("description", "")
    endpoint_url = value.get("endpoint_url")
    allowed_hosts = value.get("allowed_hosts")
    secret_ref = value.get("auth_secret_ref")

    if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 120:
        raise MCPProfileConfigurationError("MCP profile display_name is invalid")
    if not isinstance(description, str) or len(description) > 500:
        raise MCPProfileConfigurationError("MCP profile description is invalid")
    if (
        not isinstance(endpoint_url, str)
        or not endpoint_url
        or len(endpoint_url) > 2048
        or endpoint_url != endpoint_url.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in endpoint_url)
    ):
        raise MCPProfileConfigurationError("MCP profile endpoint_url is invalid")
    if not isinstance(allowed_hosts, list) or not allowed_hosts or len(allowed_hosts) > 16:
        raise MCPProfileConfigurationError("MCP profile allowed_hosts must be a non-empty list")

    try:
        parsed = urlsplit(endpoint_url)
        hostname_raw = parsed.hostname or ""
        port = parsed.port
    except ValueError as exc:
        raise MCPProfileConfigurationError("MCP profile endpoint_url is invalid") from exc

    hostname = _normalize_hostname(hostname_raw)
    if (
        parsed.scheme.lower() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (port not in (None, 443))
        or not parsed.path.startswith("/")
    ):
        raise MCPProfileConfigurationError(
            "MCP endpoint must be an HTTPS URL without userinfo, query, fragment, or non-standard port"
        )

    normalized_allowlist = {
        _normalize_hostname(host)
        for host in allowed_hosts
        if isinstance(host, str)
    }
    if len(normalized_allowlist) != len(allowed_hosts) or hostname not in normalized_allowlist:
        raise MCPProfileConfigurationError(
            "MCP endpoint hostname must exactly match a deployment allowlist entry"
        )

    if secret_ref is not None and (
        not isinstance(secret_ref, str) or not _SECRET_REF.fullmatch(secret_ref)
    ):
        raise MCPProfileConfigurationError("MCP auth_secret_ref must be an environment secret key")

    return MCPServerProfile(
        key=key,
        display_name=display_name.strip(),
        description=description.strip(),
        endpoint_url=endpoint_url,
        hostname=hostname,
        auth_secret_ref=secret_ref,
    )

def list_mcp_server_profiles() -> list[MCPServerProfile]:
    """Parse the server-owned profile map; malformed config fails closed."""
    raw = get_settings().mcp_server_profiles_json.strip()
    if not raw:
        return []
    if len(raw.encode("utf-8")) > 32_768:
        raise MCPProfileConfigurationError("MCP server profile configuration exceeds the size limit")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MCPProfileConfigurationError("MCP server profile JSON is malformed") from exc
    if not isinstance(payload, dict) or len(payload) > 32:
        raise MCPProfileConfigurationError("MCP server profile map must contain at most 32 entries")
    profiles = [_parse_profile(key, value) for key, value in payload.items()]
    if len({profile.key for profile in profiles}) != len(profiles):
        raise MCPProfileConfigurationError("MCP profile keys must be unique")
    return sorted(profiles, key=lambda profile: profile.key)

def get_mcp_server_profile(profile_key: str) -> MCPServerProfile:
    for profile in list_mcp_server_profiles():
        if profile.key == profile_key:
            return profile
    raise MCPProfileNotFoundError(profile_key)

def validate_mcp_profile_destination(profile: MCPServerProfile) -> None:
    """Reject non-public DNS answers before the SDK opens an outbound connection.

    The endpoint and exact hostname allowlist are deployment-controlled. Network
    egress policy at the runtime/container layer is still required to close the
    residual DNS-rebinding window between this check and the HTTP connection.
    """
    try:
        records = socket.getaddrinfo(
            profile.hostname,
            443,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise MCPProfileConfigurationError("MCP profile hostname did not resolve") from exc

    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for record in records:
        try:
            address = ipaddress.ip_address(record[4][0])
        except (ValueError, IndexError, TypeError) as exc:
            raise MCPProfileConfigurationError("MCP profile DNS response is invalid") from exc
        addresses.add(address)

    if not addresses or any(not address.is_global for address in addresses):
        raise MCPProfileConfigurationError("MCP profile resolves to a non-public network address")

__all__ = [
    "MCPProfileConfigurationError",
    "MCPProfileNotFoundError",
    "MCPServerProfile",
    "get_mcp_server_profile",
    "list_mcp_server_profiles",
    "validate_mcp_profile_destination",
]
