"""M33 — Publication targets + compliance.

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-25

Non-destructive: creates four new tables.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


VENUE_TYPES = (
    "journal", "conference", "workshop", "preprint",
    "book_chapter", "other",
)
CITATION_STYLES = ("numeric", "author_year", "footnote")
COMPLIANCE_SEVERITIES = ("info", "warning", "error", "blocking")
COMPLIANCE_STATUSES = ("pending", "running", "completed", "failed",
                       "skipped")
COMPLIANCE_GATES = ("pass", "pass_with_warnings", "blocked")
COMPLIANCE_CATEGORIES = (
    "title", "abstract", "keywords", "section_structure",
    "word_count", "citation_style", "bibliography_style",
    "author_metadata", "anonymization", "figure_table",
    "terminology", "references", "mandatory_declarations",
    "manuscript_completeness",
)


def upgrade() -> None:
    # ---- publication_targets --------------------------------------
    op.create_table(
        "publication_targets",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("target_code", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=True),
        sa.Column("venue", sa.Text(), nullable=False),
        sa.Column("venue_type", sa.Text(), nullable=False),
        sa.Column("citation_style", sa.Text(), nullable=False),
        sa.Column(
            "active", sa.Boolean(),
            server_default=sa.text("true"), nullable=False,
        ),
        sa.Column("paper_types", postgresql.JSONB(), nullable=True),
        sa.Column("formatting_rules", postgresql.JSONB(), nullable=True),
        sa.Column("section_rules", postgresql.JSONB(), nullable=True),
        sa.Column("word_limits", postgresql.JSONB(), nullable=True),
        sa.Column("abstract_limits", postgresql.JSONB(), nullable=True),
        sa.Column("keyword_rules", postgresql.JSONB(), nullable=True),
        sa.Column("author_rules", postgresql.JSONB(), nullable=True),
        sa.Column("anonymity_rules", postgresql.JSONB(), nullable=True),
        sa.Column("figure_table_rules", postgresql.JSONB(), nullable=True),
        sa.Column("supplementary_rules", postgresql.JSONB(), nullable=True),
        sa.Column("reference_rules", postgresql.JSONB(), nullable=True),
        sa.Column(
            "submission_checklist", postgresql.JSONB(), nullable=True,
        ),
        sa.Column(
            "profile_schema_version", sa.Text(), nullable=False,
        ),
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
        sa.Column(
            "effective_from", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "effective_to", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("venue_type", VENUE_TYPES),
            name="ck_publication_targets_venue_type",
        ),
        sa.CheckConstraint(
            _in_check("citation_style", CITATION_STYLES),
            name="ck_publication_targets_citation_style",
        ),
        sa.UniqueConstraint(
            "target_code", "profile_version",
            name="ux_publication_targets_code_version",
        ),
    )
    op.create_index(
        "ix_publication_targets_code_active", "publication_targets",
        ["target_code", "active"],
    )
    op.create_index(
        "ix_publication_targets_venue", "publication_targets", ["venue"],
    )

    # ---- publication_target_selections ----------------------------
    op.create_table(
        "publication_target_selections",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publication_targets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "selected_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("selection_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_publication_target_selections_report",
        "publication_target_selections", ["report_id"],
    )

    # ---- publication_compliance_runs ------------------------------
    op.create_table(
        "publication_compliance_runs",
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
        sa.Column(
            "target_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publication_targets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("m33_version", sa.Text(), nullable=False),
        sa.Column("rules_version", sa.Text(), nullable=False),
        sa.Column("target_profile_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
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
        sa.Column("checklist_state", postgresql.JSONB(), nullable=True),
        sa.Column("formatting_summary", postgresql.JSONB(), nullable=True),
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
            _in_check("status", COMPLIANCE_STATUSES),
            name="ck_publication_compliance_runs_status",
        ),
        sa.CheckConstraint(
            "gate IS NULL OR " + _in_check("gate", COMPLIANCE_GATES),
            name="ck_publication_compliance_runs_gate",
        ),
        sa.CheckConstraint(
            "finding_count >= 0 AND blocking_count >= 0 AND "
            "error_count >= 0 AND warning_count >= 0 AND info_count >= 0",
            name="ck_publication_compliance_runs_counts",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_publication_compliance_runs_duration",
        ),
    )
    op.create_index(
        "ix_publication_compliance_runs_project",
        "publication_compliance_runs", ["project_id"],
    )
    op.create_index(
        "ix_publication_compliance_runs_report",
        "publication_compliance_runs", ["report_id"],
    )
    op.create_index(
        "ix_publication_compliance_runs_context",
        "publication_compliance_runs",
        ["report_id", "manuscript_version_id", "target_id",
         "context_hash", "m33_version", "rules_version"],
    )
    op.create_index(
        "ux_publication_compliance_runs_completed",
        "publication_compliance_runs",
        ["report_id", "manuscript_version_id", "target_id",
         "context_hash", "m33_version", "rules_version"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )

    # ---- publication_compliance_findings --------------------------
    op.create_table(
        "publication_compliance_findings",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "compliance_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "publication_compliance_runs.id", ondelete="CASCADE",
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
            nullable=False,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("location", postgresql.JSONB(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("remediation", postgresql.JSONB(), nullable=True),
        sa.Column("finding_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("category", COMPLIANCE_CATEGORIES),
            name="ck_publication_compliance_findings_category",
        ),
        sa.CheckConstraint(
            _in_check("severity", COMPLIANCE_SEVERITIES),
            name="ck_publication_compliance_findings_severity",
        ),
    )
    op.create_index(
        "ix_publication_compliance_findings_run",
        "publication_compliance_findings", ["compliance_run_id"],
    )
    op.create_index(
        "ix_publication_compliance_findings_run_severity",
        "publication_compliance_findings",
        ["compliance_run_id", "severity"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_publication_compliance_findings_run_severity",
        table_name="publication_compliance_findings",
    )
    op.drop_index(
        "ix_publication_compliance_findings_run",
        table_name="publication_compliance_findings",
    )
    op.drop_table("publication_compliance_findings")

    op.drop_index(
        "ux_publication_compliance_runs_completed",
        table_name="publication_compliance_runs",
    )
    op.drop_index(
        "ix_publication_compliance_runs_context",
        table_name="publication_compliance_runs",
    )
    op.drop_index(
        "ix_publication_compliance_runs_report",
        table_name="publication_compliance_runs",
    )
    op.drop_index(
        "ix_publication_compliance_runs_project",
        table_name="publication_compliance_runs",
    )
    op.drop_table("publication_compliance_runs")

    op.drop_index(
        "ix_publication_target_selections_report",
        table_name="publication_target_selections",
    )
    op.drop_table("publication_target_selections")

    op.drop_index(
        "ix_publication_targets_venue", table_name="publication_targets",
    )
    op.drop_index(
        "ix_publication_targets_code_active",
        table_name="publication_targets",
    )
    op.drop_table("publication_targets")