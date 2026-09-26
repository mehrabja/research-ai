"""M25 — Knowledge / Evidence Graph ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.domain.knowledge_graph import (
    KNOWLEDGE_GRAPH_BUILD_STATUSES,
    KNOWLEDGE_GRAPH_NODE_TYPES,
    KNOWLEDGE_GRAPH_PROVENANCE_TYPES,
    KNOWLEDGE_GRAPH_RELATION_TYPES,
    KNOWLEDGE_GRAPH_VERSION_STATUSES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class KnowledgeGraphVersion(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "knowledge_graph_versions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'building'")
    )
    graph_version: Mapped[str] = mapped_column(Text, nullable=False)
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_literature_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "literature_intelligence_runs.id", ondelete="SET NULL"
        ),
        nullable=True,
    )
    research_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    node_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    edge_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    graph_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        _in_check(
            "status",
            KNOWLEDGE_GRAPH_VERSION_STATUSES,
            "ck_kg_versions_status",
        ),
        CheckConstraint("version >= 1", name="ck_kg_versions_version"),
        UniqueConstraint(
            "project_id", "version", name="ux_kg_versions_project_version"
        ),
        Index("ix_kg_versions_project", "project_id"),
        Index("ix_kg_versions_project_status", "project_id", "status"),
        Index(
            "ix_kg_versions_project_context",
            "project_id", "context_hash",
        ),
        Index(
            "ux_kg_versions_active",
            "project_id", "context_hash", "graph_version",
            unique=True,
            postgresql_where=text("status = 'ready'"),
        ),
    )


class KnowledgeGraphNode(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "knowledge_graph_nodes"

    graph_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_graph_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    node_key: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        _in_check(
            "node_type", KNOWLEDGE_GRAPH_NODE_TYPES, "ck_kg_nodes_type"
        ),
        UniqueConstraint(
            "graph_version_id", "node_key", name="ux_kg_nodes_version_key"
        ),
        Index(
            "ix_kg_nodes_version_type", "graph_version_id", "node_type"
        ),
        Index(
            "ix_kg_nodes_version_entity", "graph_version_id", "entity_id"
        ),
        Index("ix_kg_nodes_project_type", "project_id", "node_type"),
    )


class KnowledgeGraphEdge(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "knowledge_graph_edges"

    graph_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_graph_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_type: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    weight: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, server_default=text("1")
    )
    edge_key: Mapped[str] = mapped_column(Text, nullable=False)
    edge_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        _in_check(
            "relation_type",
            KNOWLEDGE_GRAPH_RELATION_TYPES,
            "ck_kg_edges_relation_type",
        ),
        _in_check(
            "provenance_type",
            KNOWLEDGE_GRAPH_PROVENANCE_TYPES,
            "ck_kg_edges_provenance_type",
        ),
        CheckConstraint(
            "source_node_id <> target_node_id",
            name="ck_kg_edges_no_self_loop",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_kg_edges_confidence_range",
        ),
        CheckConstraint("weight >= 0", name="ck_kg_edges_weight"),
        UniqueConstraint(
            "graph_version_id", "edge_key", name="ux_kg_edges_version_key"
        ),
        Index(
            "ix_kg_edges_version_source",
            "graph_version_id", "source_node_id",
        ),
        Index(
            "ix_kg_edges_version_target",
            "graph_version_id", "target_node_id",
        ),
        Index(
            "ix_kg_edges_version_relation",
            "graph_version_id", "relation_type",
        ),
        Index("ix_kg_edges_project_relation", "project_id", "relation_type"),
    )


class KnowledgeGraphBuildRun(Base):
    __tablename__ = "knowledge_graph_build_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    graph_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_graph_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    graph_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    node_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    edge_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        _in_check(
            "status",
            KNOWLEDGE_GRAPH_BUILD_STATUSES,
            "ck_kg_build_runs_status",
        ),
        CheckConstraint(
            "node_count >= 0 AND edge_count >= 0",
            name="ck_kg_build_runs_counts",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_kg_build_runs_duration",
        ),
        Index("ix_kg_build_runs_project", "project_id"),
        Index("ix_kg_build_runs_context", "project_id", "context_hash"),
        Index(
            "ux_kg_build_runs_completed",
            "project_id", "context_hash", "graph_version",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )
