"""Authentication-specific application errors."""
from __future__ import annotations

from app.core.exceptions import AppError


class RefreshTokenInvalid(AppError):
    code = "REFRESH_TOKEN_INVALID"
    status_code = 401
    message = "Refresh session is invalid or expired."


class EmailVerificationInvalid(AppError):
    code = "EMAIL_VERIFICATION_INVALID"
    status_code = 400
    message = "Email verification token is invalid or expired."


class PasswordResetInvalid(AppError):
    code = "PASSWORD_RESET_INVALID"
    status_code = 400
    message = "Password reset token is invalid or expired."


class EmailVerificationRequired(AppError):
    code = "EMAIL_VERIFICATION_REQUIRED"
    status_code = 403
    message = "Email verification is required before this account can sign in."
