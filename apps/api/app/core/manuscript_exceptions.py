from __future__ import annotations

from app.core.exceptions import AppError


class ManuscriptDraftConflictError(AppError):
    code = "MANUSCRIPT_DRAFT_CONFLICT"
    status_code = 409
    message = "Manuscript draft is based on a stale revision."


class ManuscriptDraftNotFound(AppError):
    code = "MANUSCRIPT_DRAFT_NOT_FOUND"
    status_code = 404
    message = "Manuscript draft not found."
