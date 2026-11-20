"""Authentication principal and API-key authorization guards."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, AuthenticationRequired
from app.db.models.project import Project
from app.db.models.project_file import ProjectFile
from app.db.models.report import Report
from app.db.models.source import Source
from app.security.api_scopes import required_scope_for_request, scope_allows


class APITokenScopeError(AppError):
    code = "API_TOKEN_SCOPE_FORBIDDEN"
    status_code = 403
    message = "This API token is not authorized for the requested operation."


class APITokenTargetError(AppError):
    code = "API_TOKEN_TARGET_FORBIDDEN"
    status_code = 403
    message = "This API token is restricted to a different workspace or project."


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: uuid.UUID
    auth_method: str
    token_id: uuid.UUID | None = None
    scopes: frozenset[str] = frozenset()
    workspace_ids: frozenset[str] = frozenset()
    project_ids: frozenset[str] = frozenset()

    @property
    def is_api_token(self) -> bool:
        return self.auth_method == "api_token"


def _token_target_ids(request: Request, db: Session) -> tuple[set[str], set[str], bool]:
    workspace_ids: set[str] = set()
    project_ids: set[str] = set()
    path_params = request.path_params or {}

    def add_uuid(container: set[str], value: object) -> bool:
        if value is None:
            return False
        try:
            parsed = uuid.UUID(str(value))
        except (ValueError, TypeError):
            return False
        container.add(str(parsed))
        return True

    has_target = False

    # Resolve projects to their workspace so either restriction type can be
    # enforced on any project-scoped endpoint.
    for raw in (
        path_params.get("project_id"),
        request.query_params.get("project_id"),
    ):
        try:
            pid = uuid.UUID(str(raw))
        except (ValueError, TypeError):
            continue
        project_row = db.execute(
            select(Project.workspace_id).where(Project.id == pid)
        ).first()
        if project_row:
            project_ids.add(str(pid))
            workspace_ids.add(str(project_row[0]))
            has_target = True

    has_target |= add_uuid(workspace_ids, path_params.get("workspace_id"))
    has_target |= add_uuid(workspace_ids, request.query_params.get("workspace_id"))

    for raw in (
        path_params.get("report_id"),
        request.query_params.get("report_id"),
    ):
        try:
            rid = uuid.UUID(str(raw))
        except (ValueError, TypeError):
            continue
        report_row = db.execute(
            select(Report.project_id, Project.workspace_id)
            .join(Project, Project.id == Report.project_id)
            .where(Report.id == rid)
        ).first()
        if report_row:
            project_ids.add(str(report_row[0]))
            workspace_ids.add(str(report_row[1]))
            has_target = True

    for raw in (
        path_params.get("source_id"),
        request.query_params.get("source_id"),
    ):
        try:
            sid = uuid.UUID(str(raw))
        except (ValueError, TypeError):
            continue
        source_row = db.execute(
            select(Report.project_id, Project.workspace_id)
            .join(Report, Report.id == Source.report_id)
            .join(Project, Project.id == Report.project_id)
            .where(Source.id == sid)
        ).first()
        if source_row:
            project_ids.add(str(source_row[0]))
            workspace_ids.add(str(source_row[1]))
            has_target = True

    for raw in (
        path_params.get("file_id"),
        request.query_params.get("file_id"),
    ):
        try:
            fid = uuid.UUID(str(raw))
        except (ValueError, TypeError):
            continue
        file_row = db.execute(
            select(ProjectFile.project_id, Project.workspace_id)
            .join(Project, Project.id == ProjectFile.project_id)
            .where(ProjectFile.id == fid)
        ).first()
        if file_row:
            project_ids.add(str(file_row[0]))
            workspace_ids.add(str(file_row[1]))
            has_target = True

    return workspace_ids, project_ids, has_target


def enforce_api_token_request(
    request: Request,
    db: Session,
    principal: AuthPrincipal,
) -> None:
    if not principal.is_api_token:
        return

    # API keys are machine credentials, not interactive identity proof.
    # Never allow them to alter authentication factors, mint/revoke other
    # credentials, unlink OAuth identities, or delete/export an account.
    sensitive_auth_paths = (
        "/auth/mfa",
        "/auth/oauth/",
        "/auth/api-tokens",
        "/auth/account",
        "/auth/data-export",
    )
    if any(fragment in request.url.path.lower() for fragment in sensitive_auth_paths):
        raise APITokenScopeError(
            "Interactive authentication controls require a bearer session."
        )

    settings = get_settings()
    required = required_scope_for_request(
        request.method,
        request.url.path,
        settings.api_prefix,
    )
    if required == "__forbidden__" or not scope_allows(principal.scopes, required):
        raise APITokenScopeError()

    has_restrictions = bool(principal.workspace_ids or principal.project_ids)
    if not has_restrictions:
        return

    workspace_ids, project_ids, has_target = _token_target_ids(request, db)

    path = request.url.path.lower()
    identity_only = path.endswith("/auth/me") or path.endswith("/auth/activity")
    if not has_target and not identity_only:
        raise APITokenTargetError()

    if principal.workspace_ids and (
        not workspace_ids
        or not workspace_ids.issubset(principal.workspace_ids)
    ):
        raise APITokenTargetError()

    if principal.project_ids and (
        not project_ids
        or not project_ids.issubset(principal.project_ids)
    ):
        raise APITokenTargetError()


def ensure_bearer_security_version(request: Request, user: object) -> None:
    from app.db.models.user import User

    if not isinstance(user, User):
        raise AuthenticationRequired()

    payload = getattr(request.state, "jwt_payload", None)
    if not isinstance(payload, dict):
        return

    token_version = payload.get("sv")
    if not isinstance(token_version, int):
        raise AuthenticationRequired()
    if token_version != int(user.security_version):
        raise AuthenticationRequired()


__all__ = [
    "APITokenScopeError",
    "APITokenTargetError",
    "AuthPrincipal",
    "enforce_api_token_request",
    "ensure_bearer_security_version",
]
