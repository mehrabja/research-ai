"""Register every model so ``Base.metadata`` is complete for Alembic."""
from app.db.models.academic_qa import (
    AcademicQAFinding,
    AcademicQARun,
)
from app.db.models.agent_runtime import AgentRuntimeMessage, AgentRuntimeSession
from app.db.models.ai_operation import AIOperation
from app.db.models.auth_tokens import (
    EmailVerificationToken,
    PasswordResetToken,
)
from app.db.models.billing_event import BillingEvent
from app.db.models.billing_invoice import BillingInvoice  # noqa: F401
from app.db.models.citation import (
    CitationIdentity,
    CitationRun,
    Claim,
    ClaimCitation,
    ClaimEvidence,
)
from app.db.models.code_analysis import (
    CodeAnalysis,
    CodeDependency,
    CodeSymbol,
)
from app.db.models.collaboration import (
    ManuscriptBranch,
    ManuscriptComment,
    ManuscriptReviewTask,
    ProjectCollaborationEvent,
    ProjectMember,
)
from app.db.models.data_profile import DataColumnProfile, DataProfile
from app.db.models.experiment_result import ExperimentResult
from app.db.models.file_folder import ProjectFileFolder
from app.db.models.humanization import (
    ConvergenceBestSnapshot,
    ConvergenceIteration,
    ConvergenceRun,
    ConvergenceStrategy,
    HumanizationIteration,
    HumanizationRewrite,
    HumanizationRun,
)
from app.db.models.invitation import WorkspaceInvitation  # noqa: F401
from app.db.models.jobs import Job
from app.db.models.knowledge import (
    AITellPattern,
    DetectionThreshold,
    StyleExemplar,
    TerminologyGlossary,
    VoiceProfile,
)
from app.db.models.knowledge_graph import (
    KnowledgeGraphBuildRun,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphVersion,
)
from app.db.models.literature import (
    LiteratureCluster,
    LiteratureClusterMember,
    LiteratureGap,
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptRun,
    ManuscriptSection,
    ManuscriptSectionDependency,
    ManuscriptVersion,
)
from app.db.models.manuscript_draft import ManuscriptDraft, ManuscriptDraftHistory
from app.db.models.manuscript_prose import (
    ManuscriptProseParagraph,
    ManuscriptProseRun,
    ManuscriptProseSection,
    ManuscriptProseSentence,
)
from app.db.models.membership import WorkspaceMembership  # noqa: F401
from app.db.models.metric import Metric
from app.db.models.notifications import Notification, NotificationPreference
from app.db.models.oauth import AuthIdentity, OAuthState
from app.db.models.ops import (
    CreditTransaction,
    ModelPricing,
    UsageLog,
)
from app.db.models.orchestration import (
    ResearchOrchestrationNode,
    ResearchOrchestrationRun,
)
from app.db.models.pipeline import (
    DetectionRun,
    DetectionSegment,
    GenerationRun,
    TranslationRun,
    TranslationVersion,
)
from app.db.models.plan import Plan, PlanEntitlement  # noqa: F401
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
from app.db.models.publication import (
    PublicationComplianceFinding,
    PublicationComplianceRun,
    PublicationTarget,
    PublicationTargetSelection,
)
from app.db.models.report import (
    Report,
    ReportEvent,
    ReportVersion,
    ReviewEvent,
)
from app.db.models.research_classification import (
    ClassificationEvidence,
    ProjectClassification,
)
from app.db.models.research_memory import (
    ResearchMemory,
    ResearchMemoryLink,
)
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanRun,
    ResearchPlanSection,
)
from app.db.models.research_taxonomy import (
    PaperType,
    ResearchDesign,
    ResearchDomain,
)
from app.db.models.retrieval import RetrievalResult, RetrievalRun
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.db.models.security import APIToken, UserTwoFactor
from app.db.models.session import UserSession
from app.db.models.source import (
    Chunk,
    CitationLink,
    Source,
)
from app.db.models.subscription import Subscription  # noqa: F401
from app.db.models.technical_fact import TechnicalFact
from app.db.models.technical_intelligence import TechnicalIntelligenceRun
from app.db.models.usage import UsageEvent  # noqa: F401
from app.db.models.user import User
from app.db.models.workspace import Workspace  # noqa: F401

__all__ = [
    "User",
    "Report",
    "ReportEvent",
    "ReportVersion",
    "ReviewEvent",
    "Source",
    "Chunk",
    "CitationLink",
    "GenerationRun",
    "DetectionRun",
    "DetectionSegment",
    "TranslationRun",
    "TranslationVersion",
    "HumanizationRun",
    "HumanizationIteration",
    "HumanizationRewrite",
    "ConvergenceRun",
    "ConvergenceIteration",
    "ConvergenceBestSnapshot",
    "ConvergenceStrategy",
    "VoiceProfile",
    "StyleExemplar",
    "AITellPattern",
    "DetectionThreshold",
    "TerminologyGlossary",
    "Job",
    "UsageLog",
    "ModelPricing",
    "CreditTransaction",
    "Project",
    "ProjectEvent",
    "ProjectFile",
    "ProjectFileFolder",
    "ProjectFileEvent",
    "CodeAnalysis",
    "CodeSymbol",
    "CodeDependency",
    "DataProfile",
    "DataColumnProfile",
    "ResearchDomain",
    "PaperType",
    "ResearchDesign",
    "ProjectClassification",
    "ClassificationEvidence",
    "LiteratureCluster",
    "LiteratureClusterMember",
    "LiteratureGap",
    "LiteratureIntelligenceRun",
    "ProjectLiteratureItem",
    "ResearchPlan",
    "ResearchPlanSection",
    "ResearchEvidenceRequirement",
    "ResearchPlanDependency",
    "ResearchPlanRun",
    "KnowledgeGraphVersion",
    "KnowledgeGraphNode",
    "KnowledgeGraphEdge",
    "KnowledgeGraphBuildRun",
    "RetrievalRun",
    "RetrievalResult",
    "ResearchMemory",
    "ResearchMemoryLink",
    "Manuscript",
    "ManuscriptDraft",
    "ManuscriptDraftHistory",
    "ManuscriptVersion",
    "ManuscriptSection",
    "ManuscriptSectionDependency",
    "ManuscriptRun",
    "SectionResearchRun",
    "SectionResearchEvidence",
    "TechnicalFact",
    "ExperimentResult",
    "Metric",
    "TechnicalIntelligenceRun",
    "Claim",
    "ClaimEvidence",
    "CitationIdentity",
    "ClaimCitation",
    "CitationRun",
    "Claim",
    "ClaimEvidence",
    "CitationIdentity",
    "ClaimCitation",
    "CitationRun",
    "AcademicQARun",
    "AcademicQAFinding",
    "PublicationTarget",
    "PublicationTargetSelection",
    "PublicationComplianceRun",
    "PublicationComplianceFinding",
    "ProjectMember",
    "ManuscriptBranch",
    "ManuscriptComment",
    "ManuscriptReviewTask",
    "ProjectCollaborationEvent",
    "ResearchOrchestrationRun",
    "ResearchOrchestrationNode",
    "ManuscriptProseRun",
    "ManuscriptProseSection",
    "ManuscriptProseParagraph",
    "ManuscriptProseSentence",
    "BillingEvent",
    "BillingInvoice",
    "Plan",
    "PlanEntitlement",
    "Subscription",
    "UsageEvent",
    "Workspace",
    "WorkspaceInvitation",
    "WorkspaceMembership",
    "UserSession",
    "APIToken",
    "UserTwoFactor",
    "AIOperation",
    "AgentRuntimeSession",
    "AgentRuntimeMessage",
    "Notification",
    "NotificationPreference",
    "OAuthState",
    "AuthIdentity",
    "EmailVerificationToken",
    "PasswordResetToken",
]
