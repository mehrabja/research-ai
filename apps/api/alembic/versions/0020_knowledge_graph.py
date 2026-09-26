"""M25 — Knowledge / Evidence Graph schema.

Revision ID: 0020
Revises: 0019
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

_M25_EVENTS = (
    "knowledge_graph_generation_started",
    "knowledge_graph_generation_completed",
    "knowledge_graph_generation_failed",
    "knowledge_graph_generation_skipped",
)

_M25_TABLES = (
    "knowledge_graph_versions",
    "knowledge_graph_nodes",
    "knowledge_graph_edges",
    "knowledge_graph_build_runs",
)

_EVENT_CHECK = (
    "event_type IN ("
    "'project_created','project_updated','project_archived',"
    "'classification_started','classification_completed',"
    "'classification_recomputed','classification_overridden',"
    "'classification_failed','classification_skipped',"
    "'literature_analysis_started','literature_analysis_completed',"
    "'literature_analysis_failed','literature_analysis_skipped',"
    "'literature_screening_overridden',"
    "'literature_cluster_completed','literature_gap_detected',"
    "'research_plan_generation_started',"
    "'research_plan_generation_completed',"
    "'research_plan_generation_failed',"
    "'research_plan_generation_skipped',"
    "'knowledge_graph_generation_started',"
    "'knowledge_graph_generation_completed',"
    "'knowledge_graph_generation_failed',"
    "'knowledge_graph_generation_skipped'"
    ")"
)

_NODE_TYPES = (
    "project","report","report_version","source","chunk","citation",
    "literature_item","literature_cluster","literature_gap",
    "research_plan","research_plan_section","evidence_requirement",
)

_RELATION_TYPES = (
    "project_contains_report","report_has_version","report_uses_source",
    "source_contains_chunk","citation_links_source",
    "literature_item_refers_to_source",
    "literature_item_member_of_cluster",
    "cluster_contains_literature_item",
    "gap_detected_from_cluster","plan_contains_section",
    "section_requires_evidence",
    "supports","contradicts","qualifies","extends","summarizes",
    "cites","derived_from","addresses","related_to","duplicates",
    "depends_on",
)

_PROVENANCE_TYPES = (
    "database","citation_link","source_chunk","literature_analysis",
    "research_plan","human","llm","system",
)


def _in_clause(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "knowledge_graph_versions",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False,
                  server_default=sa.text("'building'")),
        sa.Column("graph_version", sa.Text(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("source_literature_run_id", PGUUID(as_uuid=True),
                  nullable=True),
        sa.Column("research_plan_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("node_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("edge_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("graph_meta", JSONB, nullable=True),
        sa.Column("created_by", PGUUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_kg_versions_project"),
        sa.ForeignKeyConstraint(
            ["source_literature_run_id"],
            ["literature_intelligence_runs.id"], ondelete="SET NULL",
            name="fk_kg_versions_lit_run"),
        sa.ForeignKeyConstraint(
            ["research_plan_id"], ["research_plans.id"],
            ondelete="SET NULL", name="fk_kg_versions_plan"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL",
            name="fk_kg_versions_created_by"),
        sa.CheckConstraint(
            "status IN ('building','ready','superseded','failed','archived')",
            name="ck_kg_versions_status"),
        sa.CheckConstraint("version >= 1", name="ck_kg_versions_version"),
        sa.UniqueConstraint(
            "project_id", "version",
            name="ux_kg_versions_project_version"),
    )
    op.create_index("ix_kg_versions_project",
                    "knowledge_graph_versions", ["project_id"])
    op.create_index("ix_kg_versions_project_status",
                    "knowledge_graph_versions", ["project_id", "status"])
    op.create_index("ix_kg_versions_project_context",
                    "knowledge_graph_versions",
                    ["project_id", "context_hash"])
    op.create_index(
        "ux_kg_versions_active", "knowledge_graph_versions",
        ["project_id", "context_hash", "graph_version"],
        unique=True, postgresql_where=sa.text("status = 'ready'"))

    op.create_table(
        "knowledge_graph_nodes",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("graph_version_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("node_type", sa.Text(), nullable=False),
        sa.Column("node_key", sa.Text(), nullable=False),
        sa.Column("entity_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("node_meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["graph_version_id"], ["knowledge_graph_versions.id"],
            ondelete="CASCADE", name="fk_kg_nodes_version"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_kg_nodes_project"),
        sa.CheckConstraint(_in_clause("node_type", _NODE_TYPES),
                           name="ck_kg_nodes_type"),
        sa.UniqueConstraint("graph_version_id", "node_key",
                            name="ux_kg_nodes_version_key"),
    )
    op.create_index("ix_kg_nodes_version_type",
                    "knowledge_graph_nodes",
                    ["graph_version_id", "node_type"])
    op.create_index("ix_kg_nodes_version_entity",
                    "knowledge_graph_nodes",
                    ["graph_version_id", "entity_id"])
    op.create_index("ix_kg_nodes_project_type",
                    "knowledge_graph_nodes",
                    ["project_id", "node_type"])

    op.create_table(
        "knowledge_graph_edges",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("graph_version_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("source_node_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("target_node_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("provenance_type", sa.Text(), nullable=False),
        sa.Column("provenance_ref", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("weight", sa.Numeric(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("edge_key", sa.Text(), nullable=False),
        sa.Column("edge_meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["graph_version_id"], ["knowledge_graph_versions.id"],
            ondelete="CASCADE", name="fk_kg_edges_version"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_kg_edges_project"),
        sa.ForeignKeyConstraint(
            ["source_node_id"], ["knowledge_graph_nodes.id"],
            ondelete="CASCADE", name="fk_kg_edges_source"),
        sa.ForeignKeyConstraint(
            ["target_node_id"], ["knowledge_graph_nodes.id"],
            ondelete="CASCADE", name="fk_kg_edges_target"),
        sa.CheckConstraint(_in_clause("relation_type", _RELATION_TYPES),
                           name="ck_kg_edges_relation_type"),
        sa.CheckConstraint(_in_clause("provenance_type", _PROVENANCE_TYPES),
                           name="ck_kg_edges_provenance_type"),
        sa.CheckConstraint("source_node_id <> target_node_id",
                           name="ck_kg_edges_no_self_loop"),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_kg_edges_confidence_range"),
        sa.CheckConstraint("weight >= 0", name="ck_kg_edges_weight"),
        sa.UniqueConstraint("graph_version_id", "edge_key",
                            name="ux_kg_edges_version_key"),
    )
    op.create_index("ix_kg_edges_version_source",
                    "knowledge_graph_edges",
                    ["graph_version_id", "source_node_id"])
    op.create_index("ix_kg_edges_version_target",
                    "knowledge_graph_edges",
                    ["graph_version_id", "target_node_id"])
    op.create_index("ix_kg_edges_version_relation",
                    "knowledge_graph_edges",
                    ["graph_version_id", "relation_type"])
    op.create_index("ix_kg_edges_project_relation",
                    "knowledge_graph_edges",
                    ["project_id", "relation_type"])

    op.create_table(
        "knowledge_graph_build_runs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("graph_version_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("graph_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("node_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("edge_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("input_snapshot", JSONB, nullable=True),
        sa.Column("output_summary", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_kg_build_runs_project"),
        sa.ForeignKeyConstraint(
            ["graph_version_id"], ["knowledge_graph_versions.id"],
            ondelete="SET NULL", name="fk_kg_build_runs_version"),
        sa.CheckConstraint(
            "status IN ('running','completed','failed','skipped')",
            name="ck_kg_build_runs_status"),
        sa.CheckConstraint("node_count >= 0 AND edge_count >= 0",
                           name="ck_kg_build_runs_counts"),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_kg_build_runs_duration"),
    )
    op.create_index("ix_kg_build_runs_project",
                    "knowledge_graph_build_runs", ["project_id"])
    op.create_index("ix_kg_build_runs_context",
                    "knowledge_graph_build_runs",
                    ["project_id", "context_hash"])
    op.create_index(
        "ux_kg_build_runs_completed", "knowledge_graph_build_runs",
        ["project_id", "context_hash", "graph_version"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"))

    # Append-only = no UPDATE. DELETE via FK cascade is allowed so
    # project cleanup still works (same semantics as M24's
    # research_plan_runs trigger).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION knowledge_graph_build_runs_no_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'knowledge_graph_build_runs is append-only; '
                'UPDATE is forbidden';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_kg_build_runs_no_update
        BEFORE UPDATE ON knowledge_graph_build_runs
        FOR EACH ROW EXECUTE FUNCTION
            knowledge_graph_build_runs_no_update();
        """
    )

    op.drop_constraint(
        "ck_project_events_type", "project_events", type_="check"
    )
    op.create_check_constraint(
        "ck_project_events_type", "project_events", _EVENT_CHECK
    )


def downgrade() -> None:
    conn = op.get_bind()
    placeholders = ",".join(f"'{e}'" for e in _M25_EVENTS)
    event_count = conn.execute(
        sa.text(
            "SELECT count(*) FROM project_events "
            f"WHERE event_type IN ({placeholders})"
        )
    ).scalar() or 0
    if event_count:
        raise RuntimeError(
            f"Cannot downgrade to 0019: {event_count} M25 events exist."
        )

    total_rows = 0
    for tbl in _M25_TABLES:
        rows = conn.execute(
            sa.text(f"SELECT count(*) FROM {tbl}")
        ).scalar() or 0
        total_rows += int(rows)
    if total_rows:
        raise RuntimeError(
            f"Cannot downgrade to 0019: {total_rows} M25 rows exist. "
            "Refusing to destroy graph history."
        )

    op.drop_constraint(
        "ck_project_events_type", "project_events", type_="check"
    )
    op.create_check_constraint(
        "ck_project_events_type", "project_events",
        "event_type IN ("
        "'project_created','project_updated','project_archived',"
        "'classification_started','classification_completed',"
        "'classification_recomputed','classification_overridden',"
        "'classification_failed','classification_skipped',"
        "'literature_analysis_started','literature_analysis_completed',"
        "'literature_analysis_failed','literature_analysis_skipped',"
        "'literature_screening_overridden',"
        "'literature_cluster_completed','literature_gap_detected',"
        "'research_plan_generation_started',"
        "'research_plan_generation_completed',"
        "'research_plan_generation_failed',"
        "'research_plan_generation_skipped'"
        ")",
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_kg_build_runs_no_update "
        "ON knowledge_graph_build_runs"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS knowledge_graph_build_runs_no_update()"
    )
    for ix in (
        "ux_kg_build_runs_completed",
        "ix_kg_build_runs_context",
        "ix_kg_build_runs_project",
    ):
        op.drop_index(ix, table_name="knowledge_graph_build_runs")
    op.drop_table("knowledge_graph_build_runs")

    for ix in (
        "ix_kg_edges_project_relation",
        "ix_kg_edges_version_relation",
        "ix_kg_edges_version_target",
        "ix_kg_edges_version_source",
    ):
        op.drop_index(ix, table_name="knowledge_graph_edges")
    op.drop_table("knowledge_graph_edges")

    for ix in (
        "ix_kg_nodes_project_type",
        "ix_kg_nodes_version_entity",
        "ix_kg_nodes_version_type",
    ):
        op.drop_index(ix, table_name="knowledge_graph_nodes")
    op.drop_table("knowledge_graph_nodes")

    for ix in (
        "ux_kg_versions_active",
        "ix_kg_versions_project_context",
        "ix_kg_versions_project_status",
        "ix_kg_versions_project",
    ):
        op.drop_index(ix, table_name="knowledge_graph_versions")
    op.drop_table("knowledge_graph_versions")