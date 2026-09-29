"""Account export/deletion and durable security activity services."""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AccountDeletionOwnershipRequired
from app.core.security import hash_password
from app.db.models.api_token import APIToken
from app.db.models.auth_session import AuthSession
from app.db.models.audit import AuditEvent
from app.db.models.invitation import WorkspaceInvitation
from app.db.models.membership import WorkspaceMembership
from app.db.models.oauth_account import OAuthAccount
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report
from app.db.models.source import Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.services.auth import revoke_all_sessions
from app.services.audit import emit_audit


def export_user_data(db: Session, *, user_id: uuid.UUID) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("user not found")

    workspaces = db.execute(
        select(Workspace).join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,
        ).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.status == "active",
        )
    ).scalars().all()

    workspace_ids = [w.id for w in workspaces]
    projects = db.execute(
        select(Project).where(
            Project.workspace_id.in_(workspace_ids),
            Project.user_id == user_id,
        )
        if workspace_ids else select(Project).where(Project.id.is_(None))
    ).scalars().all()
    project_ids = [p.id for p in projects]

    reports = db.execute(
        select(Report).where(
            Report.project_id.in_(project_ids),
            Report.user_id == user_id,
        )
        if project_ids else select(Report).where(Report.id.is_(None))
    ).scalars().all()
    sources = db.execute(
        select(Source).where(Source.report_id.in_([r.id for r in reports]))
        if reports else select(Source).where(Source.id.is_(None))
    ).scalars().all()
    files = db.execute(
        select(ProjectFile).where(ProjectFile.project_id.in_(project_ids))
        if project_ids else select(ProjectFile).where(ProjectFile.id.is_(None))
    ).scalars().all()

    memberships = db.execute(
        select(WorkspaceMembership).where(WorkspaceMembership.user_id == user_id)
    ).scalars().all()
    invitations = db.execute(
        select(WorkspaceInvitation).where(WorkspaceInvitation.invited_by_user_id == user_id)
    ).scalars().all()

    return {
        "export_version": "1.0",
        "exported_at": datetime.now(UTC).isoformat(),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "email_verified_at": user.email_verified_at.isoformat() if user.email_verified_at else None,
            "mfa_enabled": user.mfa_enabled,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        },
        "workspaces": [
            {
                "id": str(w.id), "name": w.name, "slug": w.slug,
                "status": w.status, "created_at": w.created_at.isoformat(),
                "updated_at": w.updated_at.isoformat(),
            } for w in workspaces
        ],
        "memberships": [
            {"workspace_id": str(m.workspace_id), "role": m.role,
             "status": m.status, "created_at": m.created_at.isoformat()}
            for m in memberships
        ],
        "projects": [
            {"id": str(p.id), "workspace_id": str(p.workspace_id), "name": p.name,
             "description": p.description, "domain": p.domain,
             "research_objective": p.research_objective,
             "research_questions": p.research_questions,
             "hypotheses": p.hypotheses, "scope": p.scope,
             "constraints": p.constraints, "status": p.status,
             "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat()}
            for p in projects
        ],
        "reports": [
            {"id": str(r.id), "project_id": str(r.project_id), "topic": r.topic,
             "status": r.status, "output_language": r.output_language,
             "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat()}
            for r in reports
        ],
        "sources": [
            {"id": str(s.id), "report_id": str(s.report_id), "title": s.title,
             "url": s.url, "status": s.status, "created_at": s.created_at.isoformat()}
            for s in sources
        ],
        "files": [
            {"id": str(f.id), "project_id": str(f.project_id),
             "original_filename": f.original_filename,
             "normalized_filename": f.normalized_filename,
             "size_bytes": f.size_bytes, "sha256": f.sha256,
             "detected_mime_type": f.detected_mime_type,
             "file_kind": f.file_kind, "status": f.status,
             "created_at": f.created_at.isoformat()}
            for f in files
        ],
        "api_tokens": [
            {"id": str(t.id), "name": t.name, "token_prefix": t.token_prefix,
             "scopes": t.scopes, "allowed_workspace_ids": t.allowed_workspace_ids,
             "allowed_project_ids": t.allowed_project_ids,
             "expires_at": t.expires_at.isoformat() if t.expires_at else None,
             "revoked_at": t.revoked_at.isoformat() if t.revoked_at else None,
             "created_at": t.created_at.isoformat()}
            for t in db.execute(select(APIToken).where(APIToken.user_id == user_id)).scalars()
        ],
        "sessions": [
            {"id": str(s.id), "created_at": s.created_at.isoformat(),
             "expires_at": s.expires_at.isoformat(),
             "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
             "revoked_at": s.revoked_at.isoformat() if s.revoked_at else None}
            for s in db.execute(select(AuthSession).where(AuthSession.user_id == user_id)).scalars()
        ],
        "oauth_accounts": [
            {"provider": a.provider, "created_at": a.created_at.isoformat()}
            for a in db.execute(select(OAuthAccount).where(OAuthAccount.user_id == user_id)).scalars()
        ],
        "invitations_created": [
            {"id": str(i.id), "workspace_id": str(i.workspace_id), "email": i.email,
             "role": i.role, "created_at": i.created_at.isoformat()}
            for i in invitations
        ],
        "security_audit": [
            {"event": a.event_code, "occurred_at": a.occurred_at.isoformat(),
             "workspace_id": str(a.workspace_id) if a.workspace_id else None,
             "project_id": str(a.project_id) if a.project_id else None,
             "outcome": a.outcome, "reason": a.reason}
            for a in db.execute(
                select(AuditEvent).where(AuditEvent.actor_user_id == user_id)
                .order_by(AuditEvent.occurred_at.desc()).limit(1000)
            ).scalars()
        ],
    }


def delete_account(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> User:
    now = datetime.now(UTC)
    user = db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True)).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise ValueError("active user not found")

    owned = db.execute(
        select(Workspace).where(
            Workspace.owner_user_id == user_id,
            Workspace.status != "deleted",
        ).with_for_update()
    ).scalars().all()
    for workspace in owned:
        other_active_members = int(
            db.execute(
                select(WorkspaceMembership.user_id)
                .where(
                    WorkspaceMembership.workspace_id == workspace.id,
                    WorkspaceMembership.status == "active",
                    WorkspaceMembership.user_id != user_id,
                )
                .limit(1)
            ).first()
            is not None
        )
        if other_active_members:
            raise AccountDeletionOwnershipRequired()
        workspace.status = "deleted"

    # Outstanding invitations created by a deleted account must not
    # remain redeemable. Preserve accepted invitations as historical data.
    db.execute(
        update(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.invited_by_user_id == user_id,
            WorkspaceInvitation.accepted_at.is_(None),
            WorkspaceInvitation.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    db.execute(
        update(WorkspaceMembership)
        .where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.status == "active",
        )
        .values(status="removed")
    )
    db.execute(delete(APIToken).where(APIToken.user_id == user_id))
    db.execute(delete(OAuthAccount).where(OAuthAccount.user_id == user_id))
    revoke_all_sessions(db, user_id=user_id)

    user.security_version += 1
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_recovery_code_hashes = None
    user.deletion_requested_at = now
    user.deleted_at = now
    user.is_active = False
    user.full_name = None
    user.email = f"deleted-{user.id}@invalid.local"
    user.password_hash = hash_password(secrets.token_urlsafe(48))

    emit_audit(
        "ACCOUNT_DELETED",
        db=db,
        user_id=str(user_id),
        reason="account_deletion",
        category="authentication",
        outcome="success",
    )
    db.flush()
    return user


__all__ = ["delete_account", "export_user_data"]
