"""M34 — Collaboration event emission.

Never commits. Caller owns the transaction so the mutation and its
audit event commit atomically.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models.collaboration import ProjectCollaborationEvent


def emit_event(
    db: Session,
    *,
    project_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    event_type: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> ProjectCollaborationEvent:
    event = ProjectCollaborationEvent(
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        event_meta=metadata,
    )
    db.add(event)
    return event


__all__ = ["emit_event"]
