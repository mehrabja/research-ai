"""M23 — Literature intelligence schema.

Revision ID: 0018
Revises: 0017
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

_M23_EVENTS = (
    "literature_analysis_started",
    "literature_analysis_completed",
    "literature_analysis_failed",
    "literature_analysis_skipped",
    "literature_screening_overridden",
    "literature_cluster_completed",
    "literature_gap_detected",
)


def upgrade() -> None:
    op.create_table(
        "project_literature_items",
        sa.Column(
            "id", PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("source_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column(
            "screening_status", sa.Text(), nullable=False,
            server_default=sa.text("'discovered'"),
        ),
        sa.Column(
            "manual_override", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "manual_override_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "manual_override_by", PGUUID(as_uuid=True), nullable=True
        ),
        sa.Column("manual_override_reason", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Numeric(), nullable=True),
        sa.Column("relevance_confidence", sa.Numeric(), nullable=True),
        sa.Column("relevance_reason", sa.Text(), nullable=True),
        sa.Column("relevance_factors", JSONB, nullable=True),
        sa.Column("paper_type_code", sa.Text(), nullable=True),
        sa.Column("research_design_code", sa.Text(), nullable=True),
        sa.Column("study_summary", sa.Text(), nullable=True),
        sa.Column("methods_summary", sa.Text(), nullable=True),
        sa.Column("findings_summary", sa.Text(), nullable=True),
        sa.Column("limitations_summary", sa.Text(), nullable=True),
        sa.Column("population", sa.Text(), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("intervention", sa.Text(), nullable=True),
        sa.Column("comparator", sa.Text(), nullable=True),
        sa.Column("outcomes", JSONB, nullable=True),
        sa.Column("themes", JSONB, nullable=True),
        sa.Column("keywords", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("extraction_provenance", JSONB, nullable=True),
        sa.Column(
            "analysis_status", sa.Text(), nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.Column("analysis_version", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            ondelete="CASCADE",
            name="fk_project_literature_items_project",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"],
            ondelete="CASCADE",
            name="fk_project_literature_items_source",
        ),
        sa.ForeignKeyConstraint(
            ["manual_override_by"], ["users.id"],
            ondelete="SET NULL",
            name="fk_project_literature_items_override_by",
        ),
        sa.ForeignKeyConstraint(
            ["paper_type_code"], ["paper_types.code"],
            ondelete="SET NULL",
            name="fk_project_literature_items_paper_type",
        ),
        sa.ForeignKeyConstraint(
            ["research_design_code"], ["research_designs.code"],
            ondelete="SET NULL",
            name="fk_project_literature_items_design_code",
        ),
        sa.UniqueConstraint(
            "project_id", "source_id",
            name="ux_project_literature_items_project_source",
        ),
        sa.CheckConstraint(
            "screening_status IN "
            "('discovered','candidate','included','excluded','uncertain')",
            name="ck_project_literature_items_screening",
        ),
        sa.CheckConstraint(
            "analysis_status IN "
            "('pending','analyzing','completed','failed')",
            name="ck_project_literature_items_analysis",
        ),
        sa.CheckConstraint(
            "relevance_score IS NULL OR "
            "(relevance_score >= 0 AND relevance_score <= 1)",
            name="ck_project_literature_items_relevance_range",
        ),
        sa.CheckConstraint(
            "relevance_confidence IS NULL OR "
            "(relevance_confidence >= 0 AND relevance_confidence <= 1)",
            name="ck_project_literature_items_conf_range",
        ),
        sa.CheckConstraint(
            "sample_size IS NULL OR sample_size >= 0",
            name="ck_project_literature_items_sample_size",
        ),
    )
    op.create_index(
        "ix_project_literature_items_project_status",
        "project_literature_items",
        ["project_id", "screening_status"],
    )
    op.create_index(
        "ix_project_literature_items_project_analysis",
        "project_literature_items",
        ["project_id", "analysis_status"],
    )
    op.create_index(
        "ix_project_literature_items_source",
        "project_literature_items",
        ["source_id"],
    )

    op.create_table(
        "literature_clusters",
        sa.Column(
            "id", PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("cluster_method", sa.Text(), nullable=False),
        sa.Column("cluster_version", sa.Text(), nullable=False),
        sa.Column(
            "source_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("themes", JSONB, nullable=True),
        sa.Column("keywords", JSONB, nullable=True),
        sa.Column("disagreements", JSONB, nullable=True),
        sa.Column("limitations", JSONB, nullable=True),
        sa.Column("representative_source_ids", JSONB, nullable=True),
        sa.Column("evidence_strength", sa.Numeric(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "status", sa.Text(), nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            ondelete="CASCADE",
            name="fk_literature_clusters_project",
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed','failed')",
            name="ck_literature_clusters_status",
        ),
        sa.CheckConstraint(
            "source_count >= 0",
            name="ck_literature_clusters_source_count",
        ),
        sa.CheckConstraint(
            "evidence_strength IS NULL OR "
            "(evidence_strength >= 0 AND evidence_strength <= 1)",
            name="ck_literature_clusters_evidence_range",
        ),
    )
    op.create_index(
        "ix_literature_clusters_project_status",
        "literature_clusters",
        ["project_id", "status"],
    )

    op.create_table(
        "literature_cluster_members",
        sa.Column(
            "id", PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("cluster_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column(
            "literature_item_id", PGUUID(as_uuid=True), nullable=False
        ),
        sa.Column("similarity_score", sa.Numeric(), nullable=True),
        sa.Column("membership_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"], ["literature_clusters.id"],
            ondelete="CASCADE",
            name="fk_literature_cluster_members_cluster",
        ),
        sa.ForeignKeyConstraint(
            ["literature_item_id"], ["project_literature_items.id"],
            ondelete="CASCADE",
            name="fk_literature_cluster_members_item",
        ),
        sa.UniqueConstraint(
            "cluster_id", "literature_item_id",
            name="ux_literature_cluster_members_cluster_item",
        ),
        sa.CheckConstraint(
            "similarity_score IS NULL OR "
            "(similarity_score >= -1 AND similarity_score <= 1)",
            name="ck_literature_cluster_members_similarity",
        ),
    )
    op.create_index(
        "ix_literature_cluster_members_item",
        "literature_cluster_members",
        ["literature_item_id"],
    )

    op.create_table(
        "literature_gaps",
        sa.Column(
            "id", PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("gap_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column("supporting_source_ids", JSONB, nullable=True),
        sa.Column("supporting_cluster_ids", JSONB, nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.Text(), nullable=False,
            server_default=sa.text("'candidate'"),
        ),
        sa.Column("analysis_version", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            ondelete="CASCADE",
            name="fk_literature_gaps_project",
        ),
        sa.CheckConstraint(
            "gap_type IN ("
            "'population_gap','methodology_gap','geographic_gap',"
            "'temporal_gap','evidence_gap','outcome_gap',"
            "'comparative_gap','theoretical_gap','implementation_gap',"
            "'generalization_gap','contradiction_gap','unknown_gap'"
            ")",
            name="ck_literature_gaps_type",
        ),
        sa.CheckConstraint(
            "status IN "
            "('candidate','reviewed','accepted','rejected')",
            name="ck_literature_gaps_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_literature_gaps_confidence_range",
        ),
    )
    op.create_index(
        "ix_literature_gaps_project_status",
        "literature_gaps",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_literature_gaps_project_type",
        "literature_gaps",
        ["project_id", "gap_type"],
    )
    op.create_index(
        "ux_literature_gaps_project_fingerprint",
        "literature_gaps",
        ["project_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("fingerprint IS NOT NULL"),
    )

    op.create_table(
        "literature_intelligence_runs",
        sa.Column(
            "id", PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=True),
        sa.Column("analysis_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "source_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "included_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "excluded_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cluster_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "gap_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            ondelete="CASCADE",
            name="fk_literature_intelligence_runs_project",
        ),
        sa.CheckConstraint(
            "status IN ('completed','failed','skipped')",
            name="ck_literature_intelligence_runs_status",
        ),
        sa.CheckConstraint(
            "source_count >= 0 AND included_count >= 0 "
            "AND excluded_count >= 0 AND cluster_count >= 0 "
            "AND gap_count >= 0",
            name="ck_literature_intelligence_runs_counts",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_literature_intelligence_runs_duration",
        ),
    )
    op.create_index(
        "ix_literature_intelligence_runs_project_created",
        "literature_intelligence_runs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_literature_intelligence_runs_context_hash",
        "literature_intelligence_runs",
        ["project_id", "context_hash"],
    )
    op.create_index(
        "ux_lit_runs_unique_completed",
        "literature_intelligence_runs",
        ["project_id", "context_hash", "analysis_version"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION literature_intelligence_runs_no_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'literature_intelligence_runs is append-only; '
                'UPDATE is forbidden';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_literature_intelligence_runs_no_update
        BEFORE UPDATE ON literature_intelligence_runs
        FOR EACH ROW EXECUTE FUNCTION
            literature_intelligence_runs_no_update();
        """
    )

    op.drop_constraint(
        "ck_project_events_type", "project_events", type_="check"
    )
    op.create_check_constraint(
        "ck_project_events_type",
        "project_events",
        "event_type IN ("
        "'project_created','project_updated','project_archived',"
        "'classification_started','classification_completed',"
        "'classification_recomputed','classification_overridden',"
        "'classification_failed','classification_skipped',"
        "'literature_analysis_started','literature_analysis_completed',"
        "'literature_analysis_failed','literature_analysis_skipped',"
        "'literature_screening_overridden',"
        "'literature_cluster_completed','literature_gap_detected'"
        ")",
    )


def downgrade() -> None:
    conn = op.get_bind()
    placeholders = ",".join(f"'{e}'" for e in _M23_EVENTS)
    count = conn.execute(
        sa.text(
            "SELECT count(*) FROM project_events "
            f"WHERE event_type IN ({placeholders})"
        )
    ).scalar() or 0
    if count:
        raise RuntimeError(
            f"Cannot downgrade to 0017: {count} M23 audit events exist. "
            "Refusing to purge immutable audit history."
        )

    op.drop_constraint(
        "ck_project_events_type", "project_events", type_="check"
    )
    op.create_check_constraint(
        "ck_project_events_type",
        "project_events",
        "event_type IN ("
        "'project_created','project_updated','project_archived',"
        "'classification_started','classification_completed',"
        "'classification_recomputed','classification_overridden',"
        "'classification_failed','classification_skipped'"
        ")",
    )

    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_literature_intelligence_runs_no_update "
        "ON literature_intelligence_runs"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS "
        "literature_intelligence_runs_no_update()"
    )

    op.drop_index(
        "ux_lit_runs_unique_completed",
        table_name="literature_intelligence_runs",
    )
    op.drop_index(
        "ix_literature_intelligence_runs_context_hash",
        table_name="literature_intelligence_runs",
    )
    op.drop_index(
        "ix_literature_intelligence_runs_project_created",
        table_name="literature_intelligence_runs",
    )
    op.drop_table("literature_intelligence_runs")

    op.drop_index(
        "ux_literature_gaps_project_fingerprint",
        table_name="literature_gaps",
    )
    op.drop_index(
        "ix_literature_gaps_project_type",
        table_name="literature_gaps",
    )
    op.drop_index(
        "ix_literature_gaps_project_status",
        table_name="literature_gaps",
    )
    op.drop_table("literature_gaps")

    op.drop_index(
        "ix_literature_cluster_members_item",
        table_name="literature_cluster_members",
    )
    op.drop_table("literature_cluster_members")

    op.drop_index(
        "ix_literature_clusters_project_status",
        table_name="literature_clusters",
    )
    op.drop_table("literature_clusters")

    op.drop_index(
        "ix_project_literature_items_source",
        table_name="project_literature_items",
    )
    op.drop_index(

        "ix_project_literature_items_project_analysis",
        table_name="project_literature_items",
    )
    op.drop_index(
        "ix_project_literature_items_project_status",
        table_name="project_literature_items",
    )
    op.drop_table("project_literature_items")

__all__ = ["build_literature_context_hash"]