"""M37 — Workspace invitation service.

Security invariants enforced here:
  * raw token never persisted; only sha256 hex is stored
  * token is cryptographically random (secrets.token_urlsafe)
  * single-use: accept flips ``accepted_at``; concurrent accepts
    are serialized by ``SELECT ... FOR UPDATE`` on the row
  * role is constrained to ``INVITABLE_ROLES`` (no ``owner``)
  * creator must hold ``OP_MANAGE_MEMBERS`` on the workspace
  * acceptance requires the user's email to match the invitation
  * ``members.max`` enforced at acceptance time
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvitationAlreadyAccepted,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
    InvitationRevoked,
    InvitationRoleInvalid,
)
from app.db.models.invitation import WorkspaceInvitation
from app.db.models.membership import WorkspaceMembership
from app.db.models.user import User
from app.domain.invitation import (
    INVITABLE_ROLES,
    INVITATION_ACCEPTED,
    INVITATION_EXPIRED,
    INVITATION_PENDING,
    INVITATION_REVOKED,
    compute_state,
    default_expires_at,
    email_matches,
    generate_token,
    hash_token,
    normalize_email,
)
from app.domain.membership import MEMBERSHIP_ACTIVE, ROLE_ADMIN
from app.services import memberships as memberships_service
from app.services.audit import emit_audit

# --------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------

def create_invitation(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    email: str,
    role: str,
    invited_by_user_id: uuid.UUID,
    ttl_days: int | None = None,
) -> tuple[WorkspaceInvitation, str]:
    """Create a pending invitation.

    Returns ``(invitation, raw_token)``.  The raw token is returned
    exactly once and never persisted.
    """
    if role not in INVITABLE_ROLES:
        raise InvitationRoleInvalid()

    # Caller must be owner or admin.
    memberships_service.require_minimum_role(
        db,
        workspace_id=workspace_id,
        user_id=invited_by_user_id,
        minimum=ROLE_ADMIN,
    )

    normalized = normalize_email(email)
    if not normalized:
        raise InvitationRoleInvalid("email must not be empty")

    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    expires = (
        default_expires_at(ttl_days=ttl_days)
        if ttl_days is not None
        else default_expires_at()
    )

    inv = WorkspaceInvitation(
        workspace_id=workspace_id,
        email=normalized,
        role=role,
        token_hash=token_hash,
        expires_at=expires,
        invited_by_user_id=invited_by_user_id,
    )
    db.add(inv)
    db.flush()

    emit_audit(
        "MEMBER_INVITED",
        user_id=str(invited_by_user_id),
        workspace_id=str(workspace_id),
        invitation_id=str(inv.id),
        to_role=role,
    )
    return inv, raw_token


# --------------------------------------------------------------------------
# Accept
# --------------------------------------------------------------------------

def accept_invitation(
    db: Session,
    *,
    raw_token: str,
    user_id: uuid.UUID,
) -> WorkspaceMembership:
    """Accept a pending invitation.

    Idempotent for the same accepting user: a second call returns the
    same membership without creating a duplicate row or mutating the
    invitation further.
    """
    token_hash = hash_token(raw_token)

    inv = db.execute(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.token_hash == token_hash)
        .with_for_update()
    ).scalar_one_or_none()
    if inv is None:
        raise InvitationNotFound()

    state = compute_state(
        accepted_at=inv.accepted_at,
        revoked_at=inv.revoked_at,
        expires_at=inv.expires_at,
    )

    # Idempotent fast-path: same user already accepted -> return their
    # membership unchanged.  Safe because ``accepted_at`` is only set
    # by a successful acceptance of *this* invitation.
    if state == INVITATION_ACCEPTED:
        existing = memberships_service.get_membership(
            db, workspace_id=inv.workspace_id, user_id=user_id
        )
        if existing is not None and existing.status == MEMBERSHIP_ACTIVE:
            return existing
        raise InvitationAlreadyAccepted()

    if state == INVITATION_REVOKED:
        raise InvitationRevoked()
    if state == INVITATION_EXPIRED:
        raise InvitationExpired()
    assert state == INVITATION_PENDING

    user = db.get(User, user_id)
    if user is None:
        raise InvitationNotFound()

    if not email_matches(
        invitation_email=inv.email, user_email=user.email
    ):
        raise InvitationEmailMismatch()

    # Quota check + row lock on the workspace's member slot.
    memberships_service.ensure_member_quota(
        db, workspace_id=inv.workspace_id
    )

    membership, created = memberships_service.add_or_reactivate_member(
        db,
        workspace_id=inv.workspace_id,
        user_id=user_id,
        role=inv.role,
    )

    inv.accepted_at = datetime.now(tz=inv.expires_at.tzinfo)
    db.flush()

    emit_audit(
        "INVITATION_ACCEPTED",
        user_id=str(user_id),
        workspace_id=str(inv.workspace_id),
        invitation_id=str(inv.id),
        to_role=inv.role,
        outcome="created" if created else "reactivated",
    )
    return membership


# --------------------------------------------------------------------------
# Revoke
# --------------------------------------------------------------------------

def revoke_invitation(
    db: Session,
    *,
    invitation_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> WorkspaceInvitation:
    """Revoke a pending invitation.  Idempotent.

    Revoking an already-revoked invitation returns it unchanged.
    Revoking an already-accepted invitation raises.
    """
    inv = db.get(WorkspaceInvitation, invitation_id)
    if inv is None:
        raise InvitationNotFound()

    memberships_service.require_minimum_role(
        db,
        workspace_id=inv.workspace_id,
        user_id=actor_user_id,
        minimum=ROLE_ADMIN,
    )

    state = compute_state(
        accepted_at=inv.accepted_at,
        revoked_at=inv.revoked_at,
        expires_at=inv.expires_at,
    )
    if state == INVITATION_ACCEPTED:
        raise InvitationAlreadyAccepted()
    if state == INVITATION_REVOKED:
        return inv  # already revoked, no-op

    inv.revoked_at = datetime.now(tz=inv.expires_at.tzinfo)
    db.flush()
    return inv


# --------------------------------------------------------------------------
# List
# --------------------------------------------------------------------------

def list_invitations(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    state: str | None = None,
) -> list[WorkspaceInvitation]:
    """List invitations in a workspace, optionally filtered by state.

    Actor must be a member (any role can read the list per M37 matrix;
    stricter gating is applied by the route if desired).
    """
    memberships_service.require_active_membership(
        db, workspace_id=workspace_id, user_id=actor_user_id
    )
    rows = list(
        db.execute(
            select(WorkspaceInvitation)
            .where(WorkspaceInvitation.workspace_id == workspace_id)
            .order_by(WorkspaceInvitation.created_at.desc())
        ).scalars()
    )
    if state is None:
        return rows
    return [
        r
        for r in rows
        if compute_state(
            accepted_at=r.accepted_at,
            revoked_at=r.revoked_at,
            expires_at=r.expires_at,
        )
        == state
    ]


__all__ = [
    "accept_invitation",
    "create_invitation",
    "list_invitations",
    "revoke_invitation",
]
