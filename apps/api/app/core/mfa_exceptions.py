from __future__ import annotations

from app.core.exceptions import AppError


class MFARequired(AppError):
    code = "MFA_REQUIRED"
    status_code = 403
    message = "A valid MFA code is required."


class MFAInvalid(AppError):
    code = "MFA_INVALID"
    status_code = 400
    message = "MFA code is invalid."


class MFAAlreadyEnabled(AppError):
    code = "MFA_ALREADY_ENABLED"
    status_code = 409
    message = "MFA is already enabled."
