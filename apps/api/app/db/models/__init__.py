"""Register every model so ``Base.metadata`` is complete for Alembic."""

from app.db.models.user import User

from app.db.models.report import (
    Report,
    ReportVersion,
    ReviewEvent,
)

from app.db.models.source import (
    Source,
    Chunk,
    CitationLink,
)

from app.db.models.pipeline import (
    GenerationRun,
    DetectionRun,
    DetectionSegment,
    TranslationRun,
    TranslationVersion,
)

from app.db.models.humanization import (
    HumanizationRun,
    HumanizationIteration,
    HumanizationRewrite,
    ConvergenceRun,
    ConvergenceIteration,
    ConvergenceBestSnapshot,
    ConvergenceStrategy,
)

from app.db.models.knowledge import (
    VoiceProfile,
    StyleExemplar,
    AITellPattern,
    DetectionThreshold,
    TerminologyGlossary,
)

from app.db.models.ops import (
    Job,
    UsageLog,
    ModelPricing,
    CreditTransaction,
)


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