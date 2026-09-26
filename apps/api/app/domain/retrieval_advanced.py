"""M26 — Advanced RAG & Research Memory domain primitives."""
from __future__ import annotations

from enum import StrEnum

ADVANCED_RAG_VERSION = "m26-v1"
RESEARCH_MEMORY_VERSION = "m26-memory-v1"
RANKING_MODEL_VERSION = "m26-ranking-v1"
QUERY_DECOMPOSITION_VERSION = "m26-decomp-v1"
GRAPH_EXPANSION_VERSION = "m26-graph-v1"


class RetrievalRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RetrievalIntent(StrEnum):
    BACKGROUND = "background"
    DEFINITION = "definition"
    METHODOLOGY = "methodology"
    EMPIRICAL_EVIDENCE = "empirical_evidence"
    COMPARISON = "comparison"
    CAUSAL_EVIDENCE = "causal_evidence"
    RECENT_EVIDENCE = "recent_evidence"
    COUNTER_EVIDENCE = "counter_evidence"
    LIMITATION = "limitation"
    GAP = "gap"
    SYNTHESIS = "synthesis"
    CITATION = "citation"


class RetrievalStage(StrEnum):
    VECTOR = "vector"
    LEXICAL = "lexical"
    HYBRID = "hybrid"
    GRAPH = "graph"
    MEMORY = "memory"
    PLAN = "plan"
    RERANK = "rerank"
    DIVERSITY = "diversity"


class MemoryType(StrEnum):
    QUERY_RESULT = "query_result"
    USEFUL_SOURCE = "useful_source"
    USEFUL_CHUNK = "useful_chunk"
    EVIDENCE_PATTERN = "evidence_pattern"
    RESEARCH_THEME = "research_theme"
    RETRIEVAL_SUMMARY = "retrieval_summary"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


RETRIEVAL_RUN_STATUSES = tuple(s.value for s in RetrievalRunStatus)
RETRIEVAL_INTENTS = tuple(i.value for i in RetrievalIntent)
RETRIEVAL_STAGES = tuple(s.value for s in RetrievalStage)
MEMORY_TYPES = tuple(m.value for m in MemoryType)
MEMORY_STATUSES = tuple(m.value for m in MemoryStatus)


__all__ = [
    "ADVANCED_RAG_VERSION",
    "RESEARCH_MEMORY_VERSION",
    "RANKING_MODEL_VERSION",
    "QUERY_DECOMPOSITION_VERSION",
    "GRAPH_EXPANSION_VERSION",
    "RetrievalRunStatus",
    "RetrievalIntent",
    "RetrievalStage",
    "MemoryType",
    "MemoryStatus",
    "RETRIEVAL_RUN_STATUSES",
    "RETRIEVAL_INTENTS",
    "RETRIEVAL_STAGES",
    "MEMORY_TYPES",
    "MEMORY_STATUSES",
]
