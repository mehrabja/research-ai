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
class ProjectNotFound(AppError):
    code = "PROJECT_NOT_FOUND"
    status_code = 404
    message = "Project not found."


class ProjectReportAttachForbiddenError(AppError):
    code = "PROJECT_REPORT_ATTACH_FORBIDDEN"
    status_code = 409
    message = "Reports cannot be attached to an archived project."
class FileNotFound(AppError):
    code = "FILE_NOT_FOUND"
    status_code = 404
    message = "File not found."


class FileTooLarge(AppError):
    code = "FILE_TOO_LARGE"
    status_code = 413
    message = "File exceeds the maximum allowed size."


class InvalidFileName(AppError):
    code = "INVALID_FILE_NAME"
    status_code = 422
    message = "Filename is not valid."


class UnsupportedFileType(AppError):
    code = "UNSUPPORTED_FILE_TYPE"
    status_code = 422
    message = "File type is not supported for upload."


class DuplicateFile(AppError):
    code = "DUPLICATE_FILE"
    status_code = 409
    message = "An identical file already exists in this project."


class StorageUnavailable(AppError):
    code = "STORAGE_UNAVAILABLE"
    status_code = 503
    message = "File storage is unavailable."


class InvalidFileStatusTransition(AppError):
    code = "INVALID_FILE_STATUS_TRANSITION"
    status_code = 409
    message = "The requested file status transition is not allowed."


class ProjectArchivedForUpload(AppError):
    code = "PROJECT_ARCHIVED_FOR_UPLOAD"
    status_code = 409
    message = "Cannot upload files to an archived project."
class CodeAnalysisNotFound(AppError):
    code = "CODE_ANALYSIS_NOT_FOUND"
    status_code = 404
    message = "Code analysis not found."


class CodeAnalysisUnsupportedLanguage(AppError):
    code = "CODE_ANALYSIS_UNSUPPORTED_LANGUAGE"
    status_code = 422
    message = "This language is not supported for analysis."


class CodeAnalysisParseFailed(AppError):
    code = "CODE_ANALYSIS_PARSE_FAILED"
    status_code = 422
    message = "Source code could not be parsed."


class CodeAnalysisResourceLimit(AppError):
    code = "CODE_ANALYSIS_RESOURCE_LIMIT"
    status_code = 413
    message = "Source file exceeds analysis resource limits."


class DataProfileNotFound(AppError):
    code = "DATA_PROFILE_NOT_FOUND"
    status_code = 404
    message = "Data profile not found."


class DataProfileUnsupportedFormat(AppError):
    code = "DATA_PROFILE_UNSUPPORTED_FORMAT"
    status_code = 422
    message = "This data format is not supported for profiling."


class DataProfileMalformedData(AppError):
    code = "DATA_PROFILE_MALFORMED_DATA"
    status_code = 422
    message = "Data file is malformed and could not be profiled."


class DataProfileResourceLimit(AppError):
    code = "DATA_PROFILE_RESOURCE_LIMIT"
    status_code = 413
    message = "Data file exceeds profiling resource limits."
class ClassificationNotFound(AppError):
    code = "CLASSIFICATION_NOT_FOUND"
    status_code = 404
    message = "Classification not found."


class ClassificationTaxonomyNotFound(AppError):
    code = "CLASSIFICATION_TAXONOMY_NOT_FOUND"
    status_code = 404
    message = "Requested taxonomy item not found or inactive."


class ClassificationInvalidPayload(AppError):
    code = "CLASSIFICATION_INVALID_PAYLOAD"
    status_code = 422
    message = "Classification payload is invalid."


class ClassificationAlreadyRunning(AppError):
    code = "CLASSIFICATION_ALREADY_RUNNING"
    status_code = 409
    message = "A classification job is already running for this project."


class ClassificationResourceLimit(AppError):
    code = "CLASSIFICATION_RESOURCE_LIMIT"
    status_code = 413
    message = "Classification context exceeds resource limits."
class InvalidReportTransition(AppError):
    code = "INVALID_REPORT_TRANSITION"
    status_code = 409
    message = "The requested report status transition is not allowed."


class ReportVersionNotFound(AppError):
    code = "REPORT_VERSION_NOT_FOUND"
    status_code = 404
    message = "Report version not found."


class ReportEventValidationError(AppError):
    code = "REPORT_EVENT_VALIDATION_ERROR"
    status_code = 500
    message = "Report event validation failed."


class ReportEventVersionMismatch(AppError):
    code = "REPORT_EVENT_VERSION_MISMATCH"
    status_code = 500
    message = "Report event version does not belong to the report."


class SourceNotFound(AppError):
    code = "SOURCE_NOT_FOUND"
    status_code = 404
    message = "Source not found."


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


class EmbeddingConfigurationError(AppError):
    code = "EMBEDDING_CONFIGURATION_ERROR"
    status_code = 500
    message = "Embedding configuration is invalid."


class EmbeddingProviderUnavailableAppError(AppError):
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


class NoEvidenceAvailableError(AppError):
    code = "NO_EVIDENCE_AVAILABLE"
    status_code = 422
    message = "No evidence is available for generation."


class GenerationConfigurationError(AppError):
    code = "GENERATION_CONFIGURATION_ERROR"
    status_code = 500
    message = "Generation provider configuration is invalid."


class GenerationProviderUnavailableAppError(AppError):
    code = "GENERATION_PROVIDER_UNAVAILABLE"
    status_code = 502
    message = "Generation provider is unavailable."


class GenerationRateLimitAppError(AppError):
    code = "GENERATION_RATE_LIMITED"
    status_code = 429
    message = "Generation provider rate limit reached."


class GenerationInvalidResponseAppError(AppError):
    code = "GENERATION_INVALID_RESPONSE"
    status_code = 502
    message = "Generation provider returned an unexpected response."


class GenerationEmptyOutputError(AppError):
    code = "GENERATION_EMPTY_OUTPUT"
    status_code = 422
    message = "Generation produced empty output."


class GenerationUnknownMarkerError(AppError):
    code = "GENERATION_UNKNOWN_MARKER"
    status_code = 422
    message = "Generated text referenced an unknown evidence marker."


# --- Detection (Milestone 13) ---------------------------------------------
class DetectionAlreadyCompletedError(AppError):
    code = "DETECTION_ALREADY_COMPLETED"
    status_code = 409
    message = "Detection already completed for this version."
# --- Source Discovery (M7 missing pieces) --------------------------------
class SourceQueryInvalid(AppError):
    code = "SOURCE_QUERY_INVALID"
    status_code = 422
    message = "Source search query is invalid."


class SourceProviderUnavailable(AppError):
    code = "SOURCE_PROVIDER_UNAVAILABLE"
    status_code = 502
    message = "Source provider is unavailable."


class SourceProviderRateLimited(AppError):
    code = "SOURCE_PROVIDER_RATE_LIMITED"
    status_code = 429
    message = "Source provider rate limit reached."


class SourceProviderAuthError(AppError):
    code = "SOURCE_PROVIDER_AUTH_ERROR"
    status_code = 500
    message = "Source provider credentials are invalid."


class SourceProviderInvalidResponse(AppError):
    code = "SOURCE_PROVIDER_INVALID_RESPONSE"
    status_code = 502
    message = "Source provider returned an unexpected response."
class ResearchPlanNotFound(AppError):
    code = "RESEARCH_PLAN_NOT_FOUND"
    status_code = 404
    message = "Research plan not found."


class ResearchPlanInvalid(AppError):
    code = "RESEARCH_PLAN_INVALID"
    status_code = 409
    message = "Research plan is invalid."


class ResearchPlanDependencyCycle(AppError):
    code = "RESEARCH_PLAN_DEPENDENCY_CYCLE"
    status_code = 409
    message = "Research plan dependency cycle detected."


class ResearchPlanGenerationFailed(AppError):
    code = "RESEARCH_PLAN_GENERATION_FAILED"
    status_code = 500
    message = "Research plan generation failed."


class ResearchPlanGenerationForbidden(AppError):
    code = "RESEARCH_PLAN_GENERATION_FORBIDDEN"
    status_code = 403
    message = "Research plan generation is not permitted."


class ResearchPlanBudgetInvalid(AppError):
    code = "RESEARCH_PLAN_BUDGET_INVALID"
    status_code = 422
    message = "Research plan budget is invalid."


class ResearchPlanConfigurationInvalid(AppError):
    code = "RESEARCH_PLAN_CONFIGURATION_INVALID"
    status_code = 500
    message = "Research plan configuration is invalid."
