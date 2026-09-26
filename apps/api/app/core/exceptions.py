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
class KnowledgeGraphNotFound(AppError):
    code = "KNOWLEDGE_GRAPH_NOT_FOUND"
    status_code = 404
    message = "Knowledge graph not found."


class KnowledgeGraphInvalid(AppError):
    code = "KNOWLEDGE_GRAPH_INVALID"
    status_code = 409
    message = "Knowledge graph is invalid."


class KnowledgeGraphGenerationFailed(AppError):
    code = "KNOWLEDGE_GRAPH_GENERATION_FAILED"
    status_code = 500
    message = "Knowledge graph generation failed."


class KnowledgeGraphGenerationForbidden(AppError):
    code = "KNOWLEDGE_GRAPH_GENERATION_FORBIDDEN"
    status_code = 403
    message = "Knowledge graph generation is not permitted."


class KnowledgeGraphConfigurationInvalid(AppError):
    code = "KNOWLEDGE_GRAPH_CONFIGURATION_INVALID"
    status_code = 500
    message = "Knowledge graph configuration is invalid."
class RetrievalAdvancedNotFound(AppError):
    code = "RETRIEVAL_NOT_FOUND"
    status_code = 404
    message = "Retrieval run not found."


class RetrievalAdvancedInvalid(AppError):
    code = "RETRIEVAL_INVALID"
    status_code = 409
    message = "Retrieval request is invalid."


class RetrievalAdvancedConfigurationInvalid(AppError):
    code = "RETRIEVAL_CONFIGURATION_INVALID"
    status_code = 500
    message = "Retrieval configuration is invalid."


class ResearchMemoryNotFound(AppError):
    code = "RESEARCH_MEMORY_NOT_FOUND"
    status_code = 404
    message = "Research memory not found."
# --- Manuscript Architect (Milestone 27) ----------------------------------
class ManuscriptNotFound(AppError):
    code = "MANUSCRIPT_NOT_FOUND"
    status_code = 404
    message = "Manuscript not found."


class ManuscriptVersionNotFound(AppError):
    code = "MANUSCRIPT_VERSION_NOT_FOUND"
    status_code = 404
    message = "Manuscript version not found."


class ManuscriptSectionNotFound(AppError):
    code = "MANUSCRIPT_SECTION_NOT_FOUND"
    status_code = 404
    message = "Manuscript section not found."


class ManuscriptGenerationFailed(AppError):
    code = "MANUSCRIPT_GENERATION_FAILED"
    status_code = 500
    message = "Manuscript generation failed."


class ManuscriptGenerationForbidden(AppError):
    code = "MANUSCRIPT_GENERATION_FORBIDDEN"
    status_code = 403
    message = "Manuscript generation is not permitted."


class ManuscriptConfigurationInvalid(AppError):
    code = "MANUSCRIPT_CONFIGURATION_INVALID"
    status_code = 500
    message = "Manuscript configuration is invalid."


class ManuscriptInvalid(AppError):
    code = "MANUSCRIPT_INVALID"
    status_code = 409
    message = "Manuscript architecture is invalid."


class ManuscriptDependencyCycle(AppError):
    code = "MANUSCRIPT_DEPENDENCY_CYCLE"
    status_code = 409
    message = "Manuscript dependency cycle detected."


class ManuscriptResearchPlanMissing(AppError):
    code = "MANUSCRIPT_RESEARCH_PLAN_MISSING"
    status_code = 409
    message = "A ready research plan is required to build a manuscript."


class ManuscriptBudgetInvalid(AppError):
    code = "MANUSCRIPT_BUDGET_INVALID"
    status_code = 422
    message = "Manuscript budget is invalid."


class ManuscriptUnmappedRequirement(AppError):
    code = "MANUSCRIPT_UNMAPPED_REQUIREMENT"
    status_code = 409
    message = "Required evidence requirement has no valid M26 intent."

# --- Section Research (Milestone 28) --------------------------------------
class SectionResearchNotFound(AppError):
    code = "SECTION_RESEARCH_NOT_FOUND"
    status_code = 404
    message = "Section research run not found."


class SectionResearchInvalid(AppError):
    code = "SECTION_RESEARCH_INVALID"
    status_code = 409
    message = "Section research is invalid."


class SectionResearchContractInvalid(AppError):
    code = "SECTION_RESEARCH_CONTRACT_INVALID"
    status_code = 409
    message = "Section research contract is invalid."


class SectionResearchGenerationFailed(AppError):
    code = "SECTION_RESEARCH_GENERATION_FAILED"
    status_code = 500
    message = "Section research generation failed."


class SectionResearchConfigurationInvalid(AppError):
    code = "SECTION_RESEARCH_CONFIGURATION_INVALID"
    status_code = 500
    message = "Section research configuration is invalid."


class SectionResearchStale(AppError):
    code = "SECTION_RESEARCH_STALE"
    status_code = 409
    message = "Section research context is stale."
# --- Technical Intelligence (Milestone 29) --------------------------------
class TechnicalIntelligenceNotFound(AppError):
    code = "TECHNICAL_INTELLIGENCE_NOT_FOUND"
    status_code = 404
    message = "Technical intelligence run not found."


class TechnicalIntelligenceInvalid(AppError):
    code = "TECHNICAL_INTELLIGENCE_INVALID"
    status_code = 409
    message = "Technical intelligence request is invalid."


class TechnicalIntelligenceConfigurationInvalid(AppError):
    code = "TECHNICAL_INTELLIGENCE_CONFIGURATION_INVALID"
    status_code = 500
    message = "Technical intelligence configuration is invalid."


class TechnicalIntelligenceGenerationFailed(AppError):
    code = "TECHNICAL_INTELLIGENCE_GENERATION_FAILED"
    status_code = 500
    message = "Technical intelligence generation failed."


class TechnicalIntelligenceStale(AppError):
    code = "TECHNICAL_INTELLIGENCE_STALE"
    status_code = 409
    message = "Technical intelligence context is stale."


class TechnicalIntelligenceProvenanceMissing(AppError):
    code = "TECHNICAL_INTELLIGENCE_PROVENANCE_MISSING"
    status_code = 500
    message = "Technical evidence is missing provenance."
# --- Citation Engine (Milestone 30) ---------------------------------------
class CitationNotFound(AppError):
    code = "CITATION_NOT_FOUND"
    status_code = 404
    message = "Citation run not found."


class CitationInvalid(AppError):
    code = "CITATION_INVALID"
    status_code = 409
    message = "Citation request is invalid."


class CitationConfigurationInvalid(AppError):
    code = "CITATION_CONFIGURATION_INVALID"
    status_code = 500
    message = "Citation configuration is invalid."


class CitationGenerationFailed(AppError):
    code = "CITATION_GENERATION_FAILED"
    status_code = 500
    message = "Citation generation failed."


class CitationStale(AppError):
    code = "CITATION_STALE"
    status_code = 409
    message = "Citation context is stale."


class CitationProvenanceMissing(AppError):
    code = "CITATION_PROVENANCE_MISSING"
    status_code = 500
    message = "Citation evidence is missing provenance."


class CitationSourceMissing(AppError):
    code = "CITATION_SOURCE_MISSING"
    status_code = 500
    message = "Citation source is missing or unresolved."
# --- Academic QA (Milestone 31) ------------------------------------------
class AcademicQANotFound(AppError):
    code = "ACADEMIC_QA_NOT_FOUND"
    status_code = 404
    message = "Academic QA run not found."


class AcademicQAInvalid(AppError):
    code = "ACADEMIC_QA_INVALID"
    status_code = 409
    message = "Academic QA request is invalid."


class AcademicQAConfigurationInvalid(AppError):
    code = "ACADEMIC_QA_CONFIGURATION_INVALID"
    status_code = 500
    message = "Academic QA configuration is invalid."


class AcademicQAGenerationFailed(AppError):
    code = "ACADEMIC_QA_GENERATION_FAILED"
    status_code = 500
    message = "Academic QA generation failed."


class AcademicQAStale(AppError):
    code = "ACADEMIC_QA_STALE"
    status_code = 409
    message = "Academic QA context is stale."
# --- Advanced Humanization (Milestone 32) --------------------------------
class ManuscriptHumanizationNotFound(AppError):
    code = "MANUSCRIPT_HUMANIZATION_NOT_FOUND"
    status_code = 404
    message = "Manuscript humanization run not found."


class ManuscriptHumanizationInvalid(AppError):
    code = "MANUSCRIPT_HUMANIZATION_INVALID"
    status_code = 409
    message = "Manuscript humanization request is invalid."


class ManuscriptHumanizationConfigurationInvalid(AppError):
    code = "MANUSCRIPT_HUMANIZATION_CONFIGURATION_INVALID"
    status_code = 500
    message = "Manuscript humanization configuration is invalid."


class ManuscriptHumanizationFailed(AppError):
    code = "MANUSCRIPT_HUMANIZATION_FAILED"
    status_code = 500
    message = "Manuscript humanization failed."


class ManuscriptHumanizationStale(AppError):
    code = "MANUSCRIPT_HUMANIZATION_STALE"
    status_code = 409
    message = "Manuscript humanization context is stale."


class ManuscriptHumanizationConflict(AppError):
    code = "MANUSCRIPT_HUMANIZATION_CONFLICT"
    status_code = 409
    message = "Manuscript humanization conflict."
# --- Publication Targets (Milestone 33) ----------------------------------
class PublicationTargetNotFound(AppError):
    code = "PUBLICATION_TARGET_NOT_FOUND"
    status_code = 404
    message = "Publication target not found."


class PublicationTargetInvalid(AppError):
    code = "PUBLICATION_TARGET_INVALID"
    status_code = 409
    message = "Publication target is invalid."


class PublicationTargetConflict(AppError):
    code = "PUBLICATION_TARGET_CONFLICT"
    status_code = 409
    message = "Publication target version conflict."


class PublicationComplianceNotFound(AppError):
    code = "PUBLICATION_COMPLIANCE_NOT_FOUND"
    status_code = 404
    message = "Publication compliance run not found."


class PublicationComplianceInvalid(AppError):
    code = "PUBLICATION_COMPLIANCE_INVALID"
    status_code = 409
    message = "Publication compliance request is invalid."


class PublicationComplianceBlocked(AppError):
    code = "PUBLICATION_COMPLIANCE_BLOCKED"
    status_code = 409
    message = "Publication compliance is blocked."


class PublicationComplianceConfigurationInvalid(AppError):
    code = "PUBLICATION_COMPLIANCE_CONFIGURATION_INVALID"
    status_code = 500
    message = "Publication compliance configuration is invalid."


class PublicationComplianceFailed(AppError):
    code = "PUBLICATION_COMPLIANCE_FAILED"
    status_code = 500
    message = "Publication compliance run failed."


class PublicationComplianceStale(AppError):
    code = "PUBLICATION_COMPLIANCE_STALE"
    status_code = 409
    message = "Publication compliance context is stale."
# --- Collaboration (Milestone 34) ----------------------------------------
class CollaborationForbidden(AppError):
    code = "COLLABORATION_FORBIDDEN"
    status_code = 403
    message = "Collaboration action is not permitted."


class CollaborationNotFound(AppError):
    code = "COLLABORATION_NOT_FOUND"
    status_code = 404
    message = "Collaboration resource not found."


class CollaborationConflict(AppError):
    code = "COLLABORATION_CONFLICT"
    status_code = 409
    message = "Collaboration state conflict."


class CollaborationInvalid(AppError):
    code = "COLLABORATION_INVALID"
    status_code = 409
    message = "Collaboration request is invalid."


class CollaborationConfigurationInvalid(AppError):
    code = "COLLABORATION_CONFIGURATION_INVALID"
    status_code = 500
    message = "Collaboration configuration is invalid."


class CollaborationMemberConflict(AppError):
    code = "COLLABORATION_MEMBER_CONFLICT"
    status_code = 409
    message = "Member already exists or role change is invalid."


class VersionConflict(AppError):
    code = "VERSION_CONFLICT"
    status_code = 409
    message = "The version you are editing has changed."
# --- Agentic Orchestration (Milestone 35) --------------------------------
class OrchestrationNotFound(AppError):
    code = "ORCHESTRATION_NOT_FOUND"
    status_code = 404
    message = "Orchestration run not found."


class OrchestrationInvalid(AppError):
    code = "ORCHESTRATION_INVALID"
    status_code = 409
    message = "Orchestration request is invalid."


class OrchestrationBlocked(AppError):
    code = "ORCHESTRATION_BLOCKED"
    status_code = 409
    message = "Orchestration is blocked."


class OrchestrationApprovalRequired(AppError):
    code = "ORCHESTRATION_APPROVAL_REQUIRED"
    status_code = 409
    message = "Orchestration requires human approval."


class OrchestrationBudgetExceeded(AppError):
    code = "ORCHESTRATION_BUDGET_EXCEEDED"
    status_code = 409
    message = "Orchestration budget exceeded."


class OrchestrationStale(AppError):
    code = "ORCHESTRATION_STALE"
    status_code = 409
    message = "Orchestration context is stale."


class OrchestrationConflict(AppError):
    code = "ORCHESTRATION_CONFLICT"
    status_code = 409
    message = "Orchestration state conflict."


class OrchestrationConfigurationInvalid(AppError):
    code = "ORCHESTRATION_CONFIGURATION_INVALID"
    status_code = 500
    message = "Orchestration configuration is invalid."


class OrchestrationFailed(AppError):
    code = "ORCHESTRATION_FAILED"
    status_code = 500
    message = "Orchestration run failed."


class OrchestrationUnknownTool(AppError):
    code = "ORCHESTRATION_UNKNOWN_TOOL"
    status_code = 400
    message = "Unknown orchestration tool."
# --- Manuscript Prose Generation (Milestone 28.5) ------------------------
class ManuscriptProseNotFound(AppError):
    code = "MANUSCRIPT_PROSE_NOT_FOUND"
    status_code = 404
    message = "Manuscript prose not found."


class ManuscriptProseInvalid(AppError):
    code = "MANUSCRIPT_PROSE_INVALID"
    status_code = 409
    message = "Manuscript prose request is invalid."


class ManuscriptProseConfigurationInvalid(AppError):
    code = "MANUSCRIPT_PROSE_CONFIGURATION_INVALID"
    status_code = 500
    message = "Manuscript prose configuration is invalid."


class ManuscriptProseFailed(AppError):
    code = "MANUSCRIPT_PROSE_FAILED"
    status_code = 500
    message = "Manuscript prose generation failed."


class ManuscriptProseStale(AppError):
    code = "MANUSCRIPT_PROSE_STALE"
    status_code = 409
    message = "Manuscript prose context is stale."


class ManuscriptProseInsufficientEvidence(AppError):
    code = "MANUSCRIPT_PROSE_INSUFFICIENT_EVIDENCE"
    status_code = 409
    message = "Manuscript prose cannot be generated without evidence."


class ManuscriptProseValidationFailed(AppError):
    code = "MANUSCRIPT_PROSE_VALIDATION_FAILED"
    status_code = 422
    message = "Generated manuscript prose did not pass validation."


class ManuscriptProseConflict(AppError):
    code = "MANUSCRIPT_PROSE_CONFLICT"
    status_code = 409
    message = "Manuscript prose state conflict."
# --- M37 SaaS foundation ------------------------------------------------
class QuotaExceeded(AppError):
    """A workspace entitlement limit has been reached.

    Carries ``feature``, ``limit``, ``current`` for tests and logs.
    The HTTP response is the standard error envelope (code
    ``QUOTA_EXCEEDED``, status 409).
    """

    code = "QUOTA_EXCEEDED"
    status_code = 409

    def __init__(
        self,
        *,
        feature: str,
        limit: int,
        current: int,
    ) -> None:
        message = (
            f"Workspace quota exceeded for {feature}: "
            f"{current} >= {limit}."
        )
        super().__init__(message)
        self.feature = feature
        self.limit = limit
        self.current = current
# --- M37 SaaS foundation — workspaces & invitations --------------------
class WorkspaceNotFound(AppError):
    """Raised when a workspace is missing or the caller has no access.

    404 (not 403) to hide existence — same convention as cross-user
    project access in this repository.
    """
    code = "WORKSPACE_NOT_FOUND"
    status_code = 404
    message = "Workspace not found."


class InvitationNotFound(AppError):
    code = "INVITATION_NOT_FOUND"
    status_code = 404
    message = "Invitation not found."


class InvitationExpired(AppError):
    code = "INVITATION_EXPIRED"
    status_code = 410
    message = "Invitation has expired."


class InvitationRevoked(AppError):
    code = "INVITATION_REVOKED"
    status_code = 410
    message = "Invitation has been revoked."


class InvitationAlreadyAccepted(AppError):
    code = "INVITATION_ALREADY_ACCEPTED"
    status_code = 409
    message = "Invitation has already been accepted."


class InvitationEmailMismatch(AppError):
    code = "INVITATION_EMAIL_MISMATCH"
    status_code = 403
    message = "This invitation is addressed to a different email."


class InvitationRoleInvalid(AppError):
    code = "INVITATION_ROLE_INVALID"
    status_code = 422
    message = "Invitation role is not assignable."


class InsufficientRole(AppError):
    code = "INSUFFICIENT_ROLE"
    status_code = 403
    message = "Your workspace role does not allow this action."


class MembershipExists(AppError):
    code = "MEMBERSHIP_EXISTS"
    status_code = 409
    message = "This user is already a member of the workspace."


class LastOwner(AppError):
    code = "LAST_OWNER"
    status_code = 409
    message = "The workspace must always have an owner."
class OwnerRoleImmutable(AppError):
    """The owner's role cannot be changed directly.

    Ownership must be transferred first (which atomically sets the
    old owner to admin and the target to owner).
    """
    code = "OWNER_ROLE_IMMUTABLE"
    status_code = 409
    message = (
        "Transfer ownership before changing the owner's role."
    )
# --- M37 SaaS foundation — usage metering ------------------------------
class UsageInvalidMetric(AppError):
    code = "USAGE_INVALID_METRIC"
    status_code = 422
    message = "Usage metric is not registered."


class UsageInvalidSourceType(AppError):
    code = "USAGE_INVALID_SOURCE_TYPE"
    status_code = 422
    message = "Usage source_type is not registered."


class UsageInvalidQuantity(AppError):
    code = "USAGE_INVALID_QUANTITY"
    status_code = 422
    message = "Usage quantity must be strictly positive."


class UsageWorkspaceMissing(AppError):
    code = "USAGE_WORKSPACE_MISSING"
    status_code = 500
    message = "Usage event must be tied to a workspace."
