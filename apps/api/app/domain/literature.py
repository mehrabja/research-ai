"""M23 — Literature intelligence domain primitives."""
from __future__ import annotations

from enum import StrEnum

LITERATURE_INTELLIGENCE_VERSION = "m23.1"
SCREENING_VERSION = "m23.1"
CHARACTERIZATION_VERSION = "m23.1"
CLUSTERING_VERSION = "m23.1"
SYNTHESIS_VERSION = "m23.1"
GAP_DETECTION_VERSION = "m23.1"


class ScreeningStatus(StrEnum):
    DISCOVERED = "discovered"
    CANDIDATE = "candidate"
    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNCERTAIN = "uncertain"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class ClusterStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class GapType(StrEnum):
    POPULATION = "population_gap"
    METHODOLOGY = "methodology_gap"
    GEOGRAPHIC = "geographic_gap"
    TEMPORAL = "temporal_gap"
    EVIDENCE = "evidence_gap"
    OUTCOME = "outcome_gap"
    COMPARATIVE = "comparative_gap"
    THEORETICAL = "theoretical_gap"
    IMPLEMENTATION = "implementation_gap"
    GENERALIZATION = "generalization_gap"
    CONTRADICTION = "contradiction_gap"
    UNKNOWN = "unknown_gap"


class GapStatus(StrEnum):
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


SCREENING_STATUSES: tuple[str, ...] = tuple(s.value for s in ScreeningStatus)
ANALYSIS_STATUSES: tuple[str, ...] = tuple(s.value for s in AnalysisStatus)
CLUSTER_STATUSES: tuple[str, ...] = tuple(s.value for s in ClusterStatus)
GAP_TYPES: tuple[str, ...] = tuple(g.value for g in GapType)
GAP_STATUSES: tuple[str, ...] = tuple(g.value for g in GapStatus)
RUN_STATUSES: tuple[str, ...] = tuple(r.value for r in RunStatus)

LITERATURE_EVENT_TYPES: tuple[str, ...] = (
    "literature_analysis_started",
    "literature_analysis_completed",
    "literature_analysis_failed",
    "literature_analysis_skipped",
    "literature_screening_overridden",
    "literature_cluster_completed",
    "literature_gap_detected",
)

PROJECT_EVENT_TYPES: tuple[str, ...] = (
    "project_created",
    "project_updated",
    "project_archived",
    "classification_started",
    "classification_completed",
    "classification_recomputed",
    "classification_overridden",
    "classification_failed",
    "classification_skipped",
) + LITERATURE_EVENT_TYPES


__all__ = [
    "ANALYSIS_STATUSES",
    "AnalysisStatus",
    "CHARACTERIZATION_VERSION",
    "CLUSTERING_VERSION",
    "CLUSTER_STATUSES",
    "ClusterStatus",
    "GAP_DETECTION_VERSION",
    "GAP_STATUSES",
    "GAP_TYPES",
    "GapStatus",
    "GapType",
    "LITERATURE_EVENT_TYPES",
    "LITERATURE_INTELLIGENCE_VERSION",
    "PROJECT_EVENT_TYPES",
    "RUN_STATUSES",
    "RunStatus",
    "SCREENING_STATUSES",
    "SCREENING_VERSION",
    "ScreeningStatus",
    "SYNTHESIS_VERSION",
]
