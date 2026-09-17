"""Register every model so ``Base.metadata`` is complete for Alembic."""

from app.db.models.humanization import (
    ConvergenceBestSnapshot,
    ConvergenceIteration,
    ConvergenceRun,
    ConvergenceStrategy,
    HumanizationIteration,
    HumanizationRewrite,
    HumanizationRun,
)
from app.db.models.knowledge import (
    AITellPattern,
    DetectionThreshold,
    StyleExemplar,
    TerminologyGlossary,
    VoiceProfile,
)
from app.db.models.ops import (
    CreditTransaction,
    Job,
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
from app.db.models.report import (
    Report,
    ReportVersion,
    ReviewEvent,
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
]
