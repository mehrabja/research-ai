"""Notification application errors."""
from __future__ import annotations

from app.core.exceptions import AppError


class NotificationNotFound(AppError):
    code = "NOTIFICATION_NOT_FOUND"
    status_code = 404
    message = "Notification not found."


class WorkspaceLifecycleInvalid(AppError):
    code = "WORKSPACE_LIFECYCLE_INVALID"
    status_code = 409
    message = "Workspace lifecycle transition is not allowed."


class WorkspaceLifecycleForbidden(AppError):
    code = "WORKSPACE_LIFECYCLE_FORBIDDEN"
    status_code = 403
    message = "You are not allowed to change workspace lifecycle state."
