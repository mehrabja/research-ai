"""M25 — Knowledge / Evidence Graph domain primitives (pure)."""
from __future__ import annotations

from enum import StrEnum

KNOWLEDGE_GRAPH_VERSION = "m25-v1"
KNOWLEDGE_GRAPH_MODEL_VERSION = "m25-v1"


class KnowledgeGraphVersionStatus(StrEnum):
    BUILDING = "building"
    READY = "ready"
    SUPERSEDED = "superseded"
    FAILED = "failed"
    ARCHIVED = "archived"


class KnowledgeGraphBuildStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class KnowledgeGraphNodeType(StrEnum):
    PROJECT = "project"
    REPORT = "report"
    REPORT_VERSION = "report_version"
    SOURCE = "source"
    CHUNK = "chunk"
    CITATION = "citation"
    LITERATURE_ITEM = "literature_item"
    LITERATURE_CLUSTER = "literature_cluster"
    LITERATURE_GAP = "literature_gap"
    RESEARCH_PLAN = "research_plan"
    RESEARCH_PLAN_SECTION = "research_plan_section"
    EVIDENCE_REQUIREMENT = "evidence_requirement"


class KnowledgeGraphRelationType(StrEnum):
    PROJECT_CONTAINS_REPORT = "project_contains_report"
    REPORT_HAS_VERSION = "report_has_version"
    REPORT_USES_SOURCE = "report_uses_source"
    SOURCE_CONTAINS_CHUNK = "source_contains_chunk"
    CITATION_LINKS_SOURCE = "citation_links_source"
    LITERATURE_ITEM_REFERS_TO_SOURCE = "literature_item_refers_to_source"
    LITERATURE_ITEM_MEMBER_OF_CLUSTER = "literature_item_member_of_cluster"
    CLUSTER_CONTAINS_LITERATURE_ITEM = "cluster_contains_literature_item"
    GAP_DETECTED_FROM_CLUSTER = "gap_detected_from_cluster"
    PLAN_CONTAINS_SECTION = "plan_contains_section"
    SECTION_REQUIRES_EVIDENCE = "section_requires_evidence"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    EXTENDS = "extends"
    SUMMARIZES = "summarizes"
    CITES = "cites"
    DERIVED_FROM = "derived_from"
    ADDRESSES = "addresses"
    RELATED_TO = "related_to"
    DUPLICATES = "duplicates"
    DEPENDS_ON = "depends_on"


class KnowledgeGraphProvenanceType(StrEnum):
    DATABASE = "database"
    CITATION_LINK = "citation_link"
    SOURCE_CHUNK = "source_chunk"
    LITERATURE_ANALYSIS = "literature_analysis"
    RESEARCH_PLAN = "research_plan"
    HUMAN = "human"
    LLM = "llm"
    SYSTEM = "system"


KNOWLEDGE_GRAPH_VERSION_STATUSES = tuple(
    s.value for s in KnowledgeGraphVersionStatus
)
KNOWLEDGE_GRAPH_BUILD_STATUSES = tuple(
    s.value for s in KnowledgeGraphBuildStatus
)
KNOWLEDGE_GRAPH_NODE_TYPES = tuple(t.value for t in KnowledgeGraphNodeType)
KNOWLEDGE_GRAPH_RELATION_TYPES = tuple(
    r.value for r in KnowledgeGraphRelationType
)
KNOWLEDGE_GRAPH_PROVENANCE_TYPES = tuple(
    p.value for p in KnowledgeGraphProvenanceType
)

DETERMINISTIC_RELATION_TYPES: tuple[str, ...] = (
    KnowledgeGraphRelationType.PROJECT_CONTAINS_REPORT.value,
    KnowledgeGraphRelationType.REPORT_HAS_VERSION.value,
    KnowledgeGraphRelationType.REPORT_USES_SOURCE.value,
    KnowledgeGraphRelationType.SOURCE_CONTAINS_CHUNK.value,
    KnowledgeGraphRelationType.CITATION_LINKS_SOURCE.value,
    KnowledgeGraphRelationType.LITERATURE_ITEM_REFERS_TO_SOURCE.value,
    KnowledgeGraphRelationType.LITERATURE_ITEM_MEMBER_OF_CLUSTER.value,
    KnowledgeGraphRelationType.CLUSTER_CONTAINS_LITERATURE_ITEM.value,
    KnowledgeGraphRelationType.GAP_DETECTED_FROM_CLUSTER.value,
    KnowledgeGraphRelationType.PLAN_CONTAINS_SECTION.value,
    KnowledgeGraphRelationType.SECTION_REQUIRES_EVIDENCE.value,
)

KNOWLEDGE_GRAPH_EVENT_TYPES: tuple[str, ...] = (
    "knowledge_graph_generation_started",
    "knowledge_graph_generation_completed",
    "knowledge_graph_generation_failed",
    "knowledge_graph_generation_skipped",
)


def node_key(node_type: str, entity_id: str) -> str:
    return f"{node_type}:{entity_id}"


def edge_key(
    source_key: str,
    target_key: str,
    relation_type: str,
    provenance_type: str,
    provenance_ref: str | None,
) -> str:
    ref = provenance_ref or "-"
    return f"{source_key}|{target_key}|{relation_type}|{provenance_type}|{ref}"
