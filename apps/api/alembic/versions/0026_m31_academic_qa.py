"""M31 — Academic QA tables + ReportEvent event_type extension.

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-25

Non-destructive:
  - creates new tables
  - widens report_events CHECKs to add M31 event types
  - does not alter any existing row semantics
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


QA_CATEGORIES = (
    "claim_quality", "citation_integrity", "evidence_coverage",
    "methodology", "numerical_consistency", "structural_consistency",
    "terminology", "reproducibility", "academic_style",
)
QA_SEVERITIES = ("info", "warning", "error", "blocking")
QA_STATUSES = ("pending", "running", "completed", "failed", "skipped")
QA_CLASSIFICATIONS = ("deterministic", "model_assisted", "human_confirmed")
QA_EXECUTION_MODES = ("deterministic", "deterministic_advisory")
QA_GATES = ("pass", "pass_with_warnings", "blocked")
QA_FINDING_STATUSES = ("open", "resolved", "waived", "false_positive")

# Extended report_events event_type set after M31.
_EVENT_TYPES_V2 = (
    "status_transition", "version_created",
    "source_extracted", "source_added",
    "qa_started", "qa_completed", "qa_failed",
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Widen report_events CHECKs (non-destructive: existing rows valid).
    # ------------------------------------------------------------------
    op.drop_constraint(
        "ck_report_events_type", "report_events", type_="check",
    )
    op.create_check_constraint(
        "ck_report_events_type",
        "report_events",
        _in_check("event_type", _EVENT_TYPES_V2),
    )

    op.drop_constraint(
        "ck_report_events_shape", "report_events", type_="check",
    )
    op.create_check_constraint(
        "ck_report_events_shape",
        "report_events",
        "(event_type = 'status_transition'"
        " AND from_status IS NOT NULL"
        " AND to_status IS NOT NULL"
        " AND from_status <> to_status"
        " AND version_id IS NULL)"
        " OR "
        "(event_type = 'version_created'"
        " AND version_id IS NOT NULL"
        " AND from_status IS NULL"
        " AND to_status IS NULL)"
        " OR "
        "(event_type IN ('source_extracted','source_added',"
        "'qa_started','qa_completed','qa_failed')"
        " AND from_status IS NULL"
        " AND to_status IS NULL"
        " AND version_id IS NULL)",
    )

    # ------------------------------------------------------------------
    # academic_qa_runs
    # ------------------------------------------------------------------
    op.create_table(
        "academic_qa_runs",
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
            nullable=False,
        ),
        sa.Column(
            "manuscript_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscripts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("m31_version", sa.Text(), nullable=False),
        sa.Column("rules_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("execution_mode", sa.Text(), nullable=False),
        sa.Column(
            "finding_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "blocking_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "error_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "warning_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "info_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("gate", sa.Text(), nullable=True),
        sa.Column("dimension_scores", postgresql.JSONB(), nullable=True),
        sa.Column("summary", postgresql.JSONB(), nullable=True),
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
            _in_check("status", QA_STATUSES),
            name="ck_academic_qa_runs_status",
        ),
        sa.CheckConstraint(
            _in_check("execution_mode", QA_EXECUTION_MODES),
            name="ck_academic_qa_runs_execution_mode",
        ),
        sa.CheckConstraint(
            "gate IS NULL OR " + _in_check("gate", QA_GATES),
            name="ck_academic_qa_runs_gate",
        ),
        sa.CheckConstraint(
            "finding_count >= 0 AND blocking_count >= 0 AND "
            "error_count >= 0 AND warning_count >= 0 AND info_count >= 0",
            name="ck_academic_qa_runs_counts",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_academic_qa_runs_duration",
        ),
    )
    op.create_index(
        "ix_academic_qa_runs_project", "academic_qa_runs", ["project_id"],
    )
    op.create_index(
        "ix_academic_qa_runs_report", "academic_qa_runs", ["report_id"],
    )
    op.create_index(
        "ix_academic_qa_runs_context", "academic_qa_runs",
        ["report_id", "manuscript_version_id", "context_hash",
         "m31_version", "rules_version"],
    )
    op.create_index(
        "ux_academic_qa_runs_completed", "academic_qa_runs",
        ["report_id", "manuscript_version_id", "context_hash",
         "m31_version", "rules_version"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )

    # ------------------------------------------------------------------
    # academic_qa_findings
    # ------------------------------------------------------------------
    op.create_table(
        "academic_qa_findings",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "qa_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic_qa_runs.id", ondelete="CASCADE"),
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
            nullable=False,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "manuscript_section_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_sections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "claim_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "citation_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("citation_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("location", postgresql.JSONB(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("classification", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'open'"), nullable=False,
        ),
        sa.Column("remediation", postgresql.JSONB(), nullable=True),
        sa.Column("finding_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("category", QA_CATEGORIES),
            name="ck_academic_qa_findings_category",
        ),
        sa.CheckConstraint(
            _in_check("severity", QA_SEVERITIES),
            name="ck_academic_qa_findings_severity",
        ),
        sa.CheckConstraint(
            _in_check("classification", QA_CLASSIFICATIONS),
            name="ck_academic_qa_findings_classification",
        ),
        sa.CheckConstraint(
            _in_check("status", QA_FINDING_STATUSES),
            name="ck_academic_qa_findings_status",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_academic_qa_findings_confidence",
        ),
    )
    op.create_index(
        "ix_academic_qa_findings_run", "academic_qa_findings", ["qa_run_id"],
    )
    op.create_index(
        "ix_academic_qa_findings_project_category",
        "academic_qa_findings", ["project_id", "category"],
    )
    op.create_index(
        "ix_academic_qa_findings_run_severity",
        "academic_qa_findings", ["qa_run_id", "severity"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_academic_qa_findings_run_severity",
        table_name="academic_qa_findings",
    )
    op.drop_index(
        "ix_academic_qa_findings_project_category",
        table_name="academic_qa_findings",
    )
    op.drop_index(
        "ix_academic_qa_findings_run", table_name="academic_qa_findings",
    )
    op.drop_table("academic_qa_findings")

    op.drop_index(
        "ux_academic_qa_runs_completed", table_name="academic_qa_runs",
    )
    op.drop_index(
        "ix_academic_qa_runs_context", table_name="academic_qa_runs",
    )
    op.drop_index(
        "ix_academic_qa_runs_report", table_name="academic_qa_runs",
    )
    op.drop_index(
        "ix_academic_qa_runs_project", table_name="academic_qa_runs",
    )
    op.drop_table("academic_qa_runs")

    # Restore pre-M31 report_events CHECKs.
    op.drop_constraint(
        "ck_report_events_shape", "report_events", type_="check",
    )
    op.create_check_constraint(
        "ck_report_events_shape",
        "report_events",
        "(event_type = 'status_transition'"
        " AND from_status IS NOT NULL"
        " AND to_status IS NOT NULL"
        " AND from_status <> to_status"
        " AND version_id IS NULL)"
        " OR "
        "(event_type = 'version_created'"
        " AND version_id IS NOT NULL"
        " AND from_status IS NULL"
        " AND to_status IS NULL)"
        " OR "
        "(event_type IN ('source_extracted','source_added')"
        " AND from_status IS NULL"
        " AND to_status IS NULL"
        " AND version_id IS NULL)",
    )
    op.drop_constraint(
        "ck_report_events_type", "report_events", type_="check",
    )
    op.create_check_constraint(
        "ck_report_events_type",
        "report_events",
        "event_type IN ('status_transition','version_created',"
        "'source_extracted','source_added')",
    )