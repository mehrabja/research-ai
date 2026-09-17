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


# --- Sources (foundation for Milestone 8) ---------------------------------
class SourceNotFound(AppError):
    code = "SOURCE_NOT_FOUND"
    status_code = 404
    message = "Source not found."


# --- Extraction (Milestone 8) ---------------------------------------------
class DocumentFetchError(AppError):
    code = "DOCUMENT_FETCH_ERROR"
    status_code = 502
    message = "Failed to fetch document."


class UnsafeUrlError(AppError):
    code = "UNSAFE_URL"
    status_code = 422
    message = "The source URL is not allowed."


class DocumentTooLargeError(AppError):
    code = "DOCUMENT_TOO_LARGE"
    status_code = 413
    message = "Document exceeds the maximum allowed size."


class UnsupportedContentTypeError(AppError):
    code = "UNSUPPORTED_CONTENT_TYPE"
    status_code = 422
    message = "Document content type is not supported."


class DocumentParseError(AppError):
    code = "DOCUMENT_PARSE_ERROR"
    status_code = 422
    message = "Failed to parse document."


class NoExtractableTextError(AppError):
    code = "NO_EXTRACTABLE_TEXT"
    status_code = 422
    message = "No extractable text found in document."


class SourceDocumentUrlMissing(AppError):
    code = "SOURCE_DOCUMENT_URL_MISSING"
    status_code = 422
    message = "Source has no document URL to extract."


class ReportEventSourceMismatch(AppError):
    code = "REPORT_EVENT_SOURCE_MISMATCH"
    status_code = 500
    message = "Report event source does not belong to the report."


# --- Embeddings (Milestone 9) ---------------------------------------------
class EmbeddingConfigurationError(AppError):
    code = "EMBEDDING_CONFIGURATION_ERROR"
    status_code = 500
    message = "Embedding configuration is invalid."


class EmbeddingProviderUnavailableAppError(AppError):
    """HTTP-facing variant.

    Deliberately distinct from
    ``app.integrations.embeddings.base.EmbeddingProviderUnavailableError``
    (provider-layer, raised by adapters). The service layer maps the
    provider-layer error to this HTTP-facing one.
    """

    code = "EMBEDDING_PROVIDER_UNAVAILABLE"
    status_code = 502
    message = "Embedding provider is currently unavailable."


class EmbeddingRateLimitAppError(AppError):
    code = "EMBEDDING_RATE_LIMITED"
    status_code = 429
    message = "Embedding provider rate limit reached."


class EmbeddingInvalidResponseAppError(AppError):
    code = "EMBEDDING_INVALID_RESPONSE"
    status_code = 502
    message = "Embedding provider returned an unexpected response."


class EmbeddingsNotReadyError(AppError):
    code = "EMBEDDINGS_NOT_READY"
    status_code = 409
    message = "No embedded chunks are available for this report."


class RetrievalConfigurationError(AppError):
    code = "RETRIEVAL_CONFIGURATION_ERROR"
    status_code = 422
    message = "Retrieval configuration is invalid."


class SourceNotReadyForEmbedding(AppError):
    code = "SOURCE_NOT_READY_FOR_EMBEDDING"
    status_code = 409
    message = "Source is not ready for embedding."


# --- Jobs (Milestone 10) --------------------------------------------------
class JobNotFoundError(AppError):
    code = "JOB_NOT_FOUND"
    status_code = 404
    message = "Job not found."


class JobLeaseLostError(AppError):
    code = "JOB_LEASE_LOST"
    status_code = 409
    message = "Worker no longer owns this job."


class UnknownJobTypeError(AppError):
    code = "UNKNOWN_JOB_TYPE"
    status_code = 400
    message = "Unknown job type."


class InvalidJobStateError(AppError):
    code = "INVALID_JOB_STATE"
    status_code = 409
    message = "Job is not in a valid state for this operation."


class JobPayloadTooLargeError(AppError):
    code = "JOB_PAYLOAD_TOO_LARGE"
    status_code = 413
    message = "Job payload exceeds the maximum allowed size."
