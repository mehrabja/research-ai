"""Application exception hierarchy."""
from __future__ import annotations


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = "Internal server error."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code

        super().__init__(self.message)


class DatabaseUnavailable(AppError):
    code = "DATABASE_UNAVAILABLE"
    status_code = 503
    message = "Database is unavailable."


class UserAlreadyExists(AppError):
    code = "USER_ALREADY_EXISTS"
    status_code = 409
    message = "A user with this email already exists."


class InvalidCredentials(AppError):
    code = "INVALID_CREDENTIALS"
    status_code = 401
    message = "Invalid email or password."


class AuthenticationRequired(AppError):
    code = "AUTHENTICATION_REQUIRED"
    status_code = 401
    message = "Authentication required."


class AuthenticationRateLimited(AppError):
    code = "AUTHENTICATION_RATE_LIMITED"
    status_code = 429
    message = "Too many authentication attempts. Please try again later."


class ReportNotFound(AppError):
    code = "REPORT_NOT_FOUND"
    status_code = 404
    message = "Report not found."


class InvalidReportTransition(AppError):
    code = "INVALID_REPORT_TRANSITION"
    status_code = 409
    message = "The requested report status transition is not allowed."


class ReportVersionNotFound(AppError):
    code = "REPORT_VERSION_NOT_FOUND"
    status_code = 404
    message = "Report version not found."


class ReportEventValidationError(AppError):
    """Internal contract violation while creating a report event.

    Not client-facing. Signals that a service tried to persist an
    event with an invalid shape or an unknown status value.
    """

    code = "REPORT_EVENT_VALIDATION_ERROR"
    status_code = 500
    message = "Report event validation failed."


class ReportEventVersionMismatch(AppError):
    """Cross-report version reference in a ``version_created`` event.

    Raised when ``version_id`` does not belong to ``report_id``.
    Not client-facing: the caller (version service) validated
    ownership before invoking the event service.
    """

    code = "REPORT_EVENT_VERSION_MISMATCH"
    status_code = 500
    message = "Report event version does not belong to the report."