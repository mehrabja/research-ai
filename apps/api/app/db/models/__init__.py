"""Register every model so ``Base.metadata`` is complete for Alembic."""

from app.db.models.code_analysis import (
    CodeAnalysis,
    CodeDependency,
    CodeSymbol,
)
from app.db.models.data_profile import DataColumnProfile, DataProfile
from app.db.models.humanization import (
    ConvergenceBestSnapshot,
    ConvergenceIteration,
    ConvergenceRun,
    ConvergenceStrategy,
    HumanizationIteration,
    HumanizationRewrite,
    HumanizationRun,
)
from app.db.models.jobs import Job
from app.db.models.knowledge import (
    AITellPattern,
    DetectionThreshold,
    StyleExemplar,
    TerminologyGlossary,
    VoiceProfile,
)
from app.db.models.literature import (
    LiteratureCluster,
    LiteratureClusterMember,
    LiteratureGap,
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.ops import (
    CreditTransaction,
    ModelPricing,
    UsageLog,
)
from app.db.models.pipeline import (
    DetectionRun,
    DetectionSegment,
    GenerationRun,
    TranslationRun,
    TranslationVersion,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.project_file import ProjectFile, ProjectFileEvent
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
from app.db.models.source import (
    Chunk,
    CitationLink,
    Source,
)
from app.db.models.user import User

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
]
