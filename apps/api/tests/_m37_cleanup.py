"""M37 — shared test cleanup helper.

Deleting a test user must first delete workspaces that user owns.
``workspaces.owner_user_id`` is ``ON DELETE RESTRICT`` on purpose
(M37 tenant ownership invariant). Production FK must not be
weakened; the test lifecycle must respect it instead.

Cascades from workspace deletion remove: workspace_memberships,
workspace_invitations, subscriptions, usage_events. Projects are
``RESTRICT`` — the caller MUST delete projects first (all existing
cleanup fixtures already do).
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.workspace import Workspace


def purge_owned_workspaces(
    db: Session,
    user_ids: Sequence[uuid.UUID],
) -> None:
    """Delete workspaces owned by the given users.

    Safe when ``user_ids`` is empty. Idempotent. Does NOT touch
    workspaces the users merely belong to (membership-only).
    """
    if not user_ids:
        return
    ids = list(user_ids)
    db.execute(
        delete(Workspace).where(Workspace.owner_user_id.in_(ids))
    )


def purge_test_users(
    db: Session,
    user_ids: Sequence[uuid.UUID],
) -> None:
    """Purge owned workspaces then the users themselves."""
    if not user_ids:
        return
    purge_owned_workspaces(db, user_ids)
    db.execute(delete(User).where(User.id.in_(list(user_ids))))


__all__ = ["purge_owned_workspaces", "purge_test_users"]
