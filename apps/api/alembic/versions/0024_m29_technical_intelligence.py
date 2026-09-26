"""M29 — Technical Intelligence tables.

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


FACT_TYPES = (
    "algorithm", "library", "import", "function", "class",
    "pipeline_step", "hyperparameter", "configuration",
    "dataset_column", "dataset_characteristic",
    "input_reference", "output_reference", "experiment_identifier",
)
FACT_STATUSES = ("extracted", "validated", "rejected")
RESULT_TYPES = (
    "metric_observation", "comparison", "derived_result", "summary",
)
RESULT_STATUSES = ("parsed", "validated", "rejected")
RUN_STATUSES = ("running", "completed", "failed", "skipped")


def upgrade() -> None:
    op.create_table(
        "technical_intelligence_runs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("m29_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "fact_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "result_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "metric_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("output_summary", postgresql.JSONB(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.CheckConstraint(
            _in_check("status", RUN_STATUSES),
            name="ck_technical_intelligence_runs_status",
        ),
        sa.CheckConstraint(
            "fact_count >= 0 AND result_count >= 0 AND metric_count >= 0",
            name="ck_technical_intelligence_runs_counts",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_technical_intelligence_runs_duration",
        ),
    )
    op.create_index(
        "ix_technical_intelligence_runs_project",
        "technical_intelligence_runs", ["project_id"],
    )
    op.create_index(
        "ix_technical_intelligence_runs_context",
        "technical_intelligence_runs",
        ["project_id", "context_hash", "m29_version"],
    )
    op.create_index(
        "ux_technical_intelligence_runs_completed",
        "technical_intelligence_runs",
        ["project_id", "context_hash", "m29_version"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )

    op.create_table(
        "technical_facts",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "technical_intelligence_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "technical_intelligence_runs.id", ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "project_file_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "code_analysis_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("code_analyses.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "data_profile_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_profiles.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("fact_type", sa.Text(), nullable=False),
        sa.Column("fact_key", sa.Text(), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=True),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column(
            "confidence", sa.Float(),
            server_default=sa.text("1.0"), nullable=False,
        ),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'extracted'"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("fact_type", FACT_TYPES),
            name="ck_technical_facts_type",
        ),
        sa.CheckConstraint(
            _in_check("status", FACT_STATUSES),
            name="ck_technical_facts_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_technical_facts_confidence",
        ),
    )
    op.create_index(
        "ix_technical_facts_run", "technical_facts",
        ["technical_intelligence_run_id"],
    )
    op.create_index(
        "ix_technical_facts_run_type", "technical_facts",
        ["technical_intelligence_run_id", "fact_type"],
    )
    op.create_index(
        "ix_technical_facts_run_key", "technical_facts",
        ["technical_intelligence_run_id", "fact_key"],
    )
    op.create_index(
        "ix_technical_facts_project", "technical_facts", ["project_id"],
    )

    op.create_table(
        "experiment_results",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "technical_intelligence_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "technical_intelligence_runs.id", ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "technical_fact_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technical_facts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "project_file_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("result_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("experiment_key", sa.Text(), nullable=True),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'parsed'"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("result_type", RESULT_TYPES),
            name="ck_experiment_results_type",
        ),
        sa.CheckConstraint(
            _in_check("status", RESULT_STATUSES),
            name="ck_experiment_results_status",
        ),
    )
    op.create_index(
        "ix_experiment_results_run", "experiment_results",
        ["technical_intelligence_run_id"],
    )
    op.create_index(
        "ix_experiment_results_run_type", "experiment_results",
        ["technical_intelligence_run_id", "result_type"],
    )
    op.create_index(
        "ix_experiment_results_run_key", "experiment_results",
        ["technical_intelligence_run_id", "experiment_key"],
    )
    op.create_index(
        "ix_experiment_results_file", "experiment_results",
        ["project_file_id"],
    )

    op.create_table(
        "metrics",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "technical_intelligence_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "technical_intelligence_runs.id", ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "experiment_result_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("split", sa.Text(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("baseline_value", sa.Float(), nullable=True),
        sa.Column("delta_value", sa.Float(), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(),
            server_default=sa.text("false"), nullable=False,
        ),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'parsed'"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "direction IS NULL OR direction IN ('higher','lower')",
            name="ck_metrics_direction",
        ),
        sa.CheckConstraint(
            "status IN ('parsed','validated','rejected')",
            name="ck_metrics_status",
        ),
        sa.CheckConstraint(
            "value_numeric IS NOT NULL OR value_text IS NOT NULL",
            name="ck_metrics_value_present",
        ),
    )
    op.create_index("ix_metrics_run", "metrics",
                    ["technical_intelligence_run_id"])
    op.create_index(
        "ix_metrics_run_normalized", "metrics",
        ["technical_intelligence_run_id", "normalized_name"],
    )
    op.create_index("ix_metrics_result", "metrics",
                    ["experiment_result_id"])


def downgrade() -> None:
    op.drop_index("ix_metrics_result", table_name="metrics")
    op.drop_index("ix_metrics_run_normalized", table_name="metrics")
    op.drop_index("ix_metrics_run", table_name="metrics")
    op.drop_table("metrics")

    op.drop_index(
        "ix_experiment_results_file", table_name="experiment_results",
    )
    op.drop_index(
        "ix_experiment_results_run_key", table_name="experiment_results",
    )
    op.drop_index(
        "ix_experiment_results_run_type", table_name="experiment_results",
    )
    op.drop_index(
        "ix_experiment_results_run", table_name="experiment_results",
    )
    op.drop_table("experiment_results")

    op.drop_index("ix_technical_facts_project", table_name="technical_facts")
    op.drop_index(
        "ix_technical_facts_run_key", table_name="technical_facts",
    )
    op.drop_index(
        "ix_technical_facts_run_type", table_name="technical_facts",
    )
    op.drop_index("ix_technical_facts_run", table_name="technical_facts")
    op.drop_table("technical_facts")

    op.drop_index(
        "ux_technical_intelligence_runs_completed",
        table_name="technical_intelligence_runs",
    )
    op.drop_index(
        "ix_technical_intelligence_runs_context",
        table_name="technical_intelligence_runs",
    )
    op.drop_index(
        "ix_technical_intelligence_runs_project",
        table_name="technical_intelligence_runs",
    )
    op.drop_table("technical_intelligence_runs")