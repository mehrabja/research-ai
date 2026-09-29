"""API token scope and target-restriction policy.

Scopes are deliberately coarse and resource-oriented so they are easy to
reason about and audit. read:* / write:* are supported convenience
wildcards; * grants every API capability and should only be used for
explicitly privileged automation tokens.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

SCOPE_READ = "read"
SCOPE_WRITE = "write"
SCOPE_MANAGE = "manage"
DEFAULT_SCOPES: tuple[str, ...] = ("read:*",)
_UNKNOWN_RESOURCE = "__unknown__"

RESOURCES: frozenset[str] = frozenset({
    "auth", "api_tokens", "workspaces", "projects", "reports", "sources",
    "files", "folders", "evidence", "citations", "literature", "plan",
    "knowledge", "rag", "academic_qa", "manuscript", "reviews",
    "publication", "jobs", "notifications", "search", "intelligence",
    "classification", "orchestration", "canvas", "pdf", "usage",
    "billing", "providers", "embeddings", "translation", "humanization",
    "detection", "dashboard", "research",
})


def normalize_scopes(scopes: Iterable[str]) -> tuple[str, ...]:
    values: set[str] = set()
    for raw in scopes:
        if not isinstance(raw, str):
            continue
        value = raw.strip().lower()
        if not value:
            continue
        if value == "*" or value in {"read:*", "write:*", "manage:*"}:
            values.add(value)
            continue
        parts = value.split(":", 1)
        if len(parts) != 2 or parts[0] not in {SCOPE_READ, SCOPE_WRITE, SCOPE_MANAGE}:
            raise ValueError(f"invalid API token scope: {raw!r}")
        resource = parts[1]
        if resource == "*" or resource in RESOURCES:
            values.add(f"{parts[0]}:{resource}")
        else:
            raise ValueError(f"unknown API token resource: {resource!r}")
    if not values:
        raise ValueError("at least one API token scope is required")
    return tuple(sorted(values))


def scope_allows(scopes: Iterable[str], required: str) -> bool:
    granted = {s.strip().lower() for s in scopes if isinstance(s, str)}
    required = required.strip().lower()
    if "*" in granted or required in granted:
        return True
    try:
        action, _resource = required.split(":", 1)
    except ValueError:
        return False
    return f"{action}:*" in granted


def resource_for_path(path: str, api_prefix: str = "/api/v1") -> str:
    raw = path
    if api_prefix and raw.startswith(api_prefix):
        raw = raw[len(api_prefix):]
    segments = [s for s in raw.split("/") if s]
    if not segments:
        return "auth"
    first = segments[0].lower()
    aliases = {
        "auth": "auth", "workspaces": "workspaces", "projects": "projects",
        "reports": "reports", "sources": "sources", "files": "files",
        "folders": "folders", "search": "search", "jobs": "jobs",
        "notifications": "notifications", "evidence": "evidence",
        "citations": "citations", "literature": "literature", "plan": "plan",
        "knowledge-graph": "knowledge", "knowledge": "knowledge", "rag": "rag",
        "academic-qa": "academic_qa", "manuscript": "manuscript",
        "reviews": "reviews", "publication": "publication",
        "orchestration": "orchestration", "research-canvas": "canvas",
        "canvas": "canvas", "pdf-workspace": "pdf", "usage": "usage",
        "usage-billing": "billing", "billing": "billing", "providers": "providers",
        "embeddings": "embeddings", "translation": "translation",
        "humanization": "humanization", "detection": "detection",
        "intelligence": "intelligence", "classification": "classification",
        "research": "research", "dashboard": "dashboard",
    }
    return aliases.get(first, first if first in RESOURCES else _UNKNOWN_RESOURCE)


def required_scope_for_request(method: str, path: str, api_prefix: str = "/api/v1") -> str:
    resource = resource_for_path(path, api_prefix)
    method = method.upper()
    if resource == _UNKNOWN_RESOURCE:
        return "__forbidden__"
    if resource == "auth" and "/api-tokens" in path:
        return "read:api_tokens" if method == "GET" else "manage:api_tokens"
    if resource == "api_tokens":
        return "read:api_tokens" if method == "GET" else "manage:api_tokens"
    if resource == "auth" and any(x in path for x in ("/mfa", "/oauth/")):
        return "manage:auth"
    if resource == "workspaces" and any(x in path for x in ("/members", "/invitations", "/suspend", "/reactivate")) and method != "GET":
        return "manage:workspaces"
    if resource == "billing" and method != "GET":
        return "manage:billing"
    if resource == "providers" and method != "GET":
        return "manage:providers"
    action = SCOPE_READ if method in {"GET", "HEAD", "OPTIONS"} else SCOPE_WRITE
    return f"{action}:{resource}"


@dataclass(frozen=True)
class TokenRestriction:
    workspace_ids: frozenset[str]
    project_ids: frozenset[str]


__all__ = [
    "DEFAULT_SCOPES", "RESOURCES", "TokenRestriction",
    "normalize_scopes", "required_scope_for_request", "resource_for_path", "scope_allows",
]
