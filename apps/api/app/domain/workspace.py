"""M37 — Workspace (tenant) domain primitives."""
from __future__ import annotations

import re
import secrets

WORKSPACE_STATUS_ACTIVE = "active"
WORKSPACE_STATUS_SUSPENDED = "suspended"
WORKSPACE_STATUS_DELETED = "deleted"

WORKSPACE_STATUSES: tuple[str, ...] = (
    WORKSPACE_STATUS_ACTIVE,
    WORKSPACE_STATUS_SUSPENDED,
    WORKSPACE_STATUS_DELETED,
)

# Statuses in which a workspace may perform business mutations.
WORKSPACE_MUTABLE_STATUSES: tuple[str, ...] = (WORKSPACE_STATUS_ACTIVE,)

# Statuses in which read access is still allowed.
WORKSPACE_READABLE_STATUSES: tuple[str, ...] = (
    WORKSPACE_STATUS_ACTIVE,
    WORKSPACE_STATUS_SUSPENDED,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MIN = 3
_SLUG_MAX = 64
_SLUG_FALLBACK = "ws"


def slugify(name: str) -> str:
    """Return a URL-safe slug body.

    Guarantees ``3 <= len(result) <= 64`` so the DB CHECK always
    passes. Non-ASCII input (e.g. Persian) is intentionally reduced
    to an ASCII slug; a random suffix preserves uniqueness.
    """
    s = _SLUG_RE.sub("-", (name or "").strip().lower()).strip("-")
    if not s:
        s = _SLUG_FALLBACK
    if len(s) < _SLUG_MIN:
        s = f"{s}-{secrets.token_hex(4)}".strip("-")
    return s[:_SLUG_MAX]


def is_mutable(status: str) -> bool:
    return status in WORKSPACE_MUTABLE_STATUSES


def is_readable(status: str) -> bool:
    return status in WORKSPACE_READABLE_STATUSES


__all__ = [
    "WORKSPACE_MUTABLE_STATUSES",
    "WORKSPACE_READABLE_STATUSES",
    "WORKSPACE_STATUSES",
    "WORKSPACE_STATUS_ACTIVE",
    "WORKSPACE_STATUS_DELETED",
    "WORKSPACE_STATUS_SUSPENDED",
    "is_mutable",
    "is_readable",
    "slugify",
]
