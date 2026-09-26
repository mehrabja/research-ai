"""M37 — Workspace membership / role policy.

Centralised role matrix. Business services MUST call
``role_allows()`` instead of re-implementing role checks.
"""
from __future__ import annotations

# ----- Roles ---------------------------------------------------------------
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_VIEWER = "viewer"

ROLES: tuple[str, ...] = (ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEWER)

# ----- Membership statuses -------------------------------------------------
MEMBERSHIP_ACTIVE = "active"
MEMBERSHIP_REMOVED = "removed"

MEMBERSHIP_STATUSES: tuple[str, ...] = (
    MEMBERSHIP_ACTIVE,
    MEMBERSHIP_REMOVED,
)

# ----- Role rank -----------------------------------------------------------
_ROLE_RANK = {
    ROLE_VIEWER: 10,
    ROLE_MEMBER: 20,
    ROLE_ADMIN: 30,
    ROLE_OWNER: 40,
}

# ----- Operations ----------------------------------------------------------
OP_READ_WORKSPACE = "read_workspace"
OP_UPDATE_WORKSPACE = "update_workspace"
OP_MANAGE_MEMBERS = "manage_members"
OP_MANAGE_BILLING = "manage_billing"
OP_DELETE_WORKSPACE = "delete_workspace"
OP_CREATE_PROJECT = "create_project"
OP_UPDATE_PROJECT = "update_project"
OP_CREATE_REPORT = "create_report"
OP_MANAGE_USAGE = "manage_usage"
OP_VIEW_USAGE = "view_usage"
OP_VIEW_PLAN = "view_plan"
OP_VIEW_SUBSCRIPTION = "view_subscription"

OPERATIONS: tuple[str, ...] = (
    OP_READ_WORKSPACE,
    OP_UPDATE_WORKSPACE,
    OP_MANAGE_MEMBERS,
    OP_MANAGE_BILLING,
    OP_DELETE_WORKSPACE,
    OP_CREATE_PROJECT,
    OP_UPDATE_PROJECT,
    OP_CREATE_REPORT,
    OP_MANAGE_USAGE,
    OP_VIEW_USAGE,
    OP_VIEW_PLAN,
    OP_VIEW_SUBSCRIPTION,
)

_READ_OPS = frozenset(
    {OP_READ_WORKSPACE, OP_VIEW_USAGE, OP_VIEW_PLAN, OP_VIEW_SUBSCRIPTION}
)
_OWNER_ONLY = frozenset({OP_DELETE_WORKSPACE, OP_MANAGE_BILLING})
_ADMIN_OPS = frozenset({OP_UPDATE_WORKSPACE, OP_MANAGE_MEMBERS})
_MEMBER_OPS = frozenset(
    {
        OP_CREATE_PROJECT,
        OP_UPDATE_PROJECT,
        OP_CREATE_REPORT,
        OP_MANAGE_USAGE,
    }
)

_ROLE_MATRIX: dict[str, frozenset[str]] = {
    ROLE_OWNER: frozenset(OPERATIONS),
    ROLE_ADMIN: _READ_OPS | _ADMIN_OPS | _MEMBER_OPS,
    ROLE_MEMBER: _READ_OPS | _MEMBER_OPS,
    ROLE_VIEWER: _READ_OPS,
}


def role_allows(role: str, operation: str) -> bool:
    allowed = _ROLE_MATRIX.get(role)
    if allowed is None:
        return False
    return operation in allowed


def role_at_least(role: str, minimum: str) -> bool:
    return _ROLE_RANK.get(role, 0) >= _ROLE_RANK.get(minimum, 0)


__all__ = [
    "MEMBERSHIP_ACTIVE",
    "MEMBERSHIP_REMOVED",
    "MEMBERSHIP_STATUSES",
    "OPERATIONS",
    "OP_CREATE_PROJECT",
    "OP_CREATE_REPORT",
    "OP_DELETE_WORKSPACE",
    "OP_MANAGE_BILLING",
    "OP_MANAGE_MEMBERS",
    "OP_MANAGE_USAGE",
    "OP_READ_WORKSPACE",
    "OP_UPDATE_PROJECT",
    "OP_UPDATE_WORKSPACE",
    "OP_VIEW_PLAN",
    "OP_VIEW_SUBSCRIPTION",
    "OP_VIEW_USAGE",
    "ROLES",
    "ROLE_ADMIN",
    "ROLE_MEMBER",
    "ROLE_OWNER",
    "ROLE_VIEWER",
    "role_allows",
    "role_at_least",
]
