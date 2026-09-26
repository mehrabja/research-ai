"""M27 — Manuscript Architect tables.

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


MANUSCRIPT_STATUSES = ("draft", "ready", "superseded", "failed", "archived")
MANUSCRIPT_VERSION_STATUSES = ("draft", "ready", "superseded", "failed")
MANUSCRIPT_RUN_STATUSES = ("running", "completed", "failed", "skipped")
MANUSCRIPT_DEPENDENCY_TYPES = ("requires", "informs", "precedes")


def upgrade() -> None:
    # 1) manuscripts (WITHOUT current_version_id FK yet)
    op.create_table(
        "manuscripts",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "current_version_id", postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("architecture_version", sa.Text(), nullable=False),
        sa.Column("template_version", sa.Text(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("status", MANUSCRIPT_STATUSES),
            name="ck_manuscripts_status",
        ),
        sa.UniqueConstraint("report_id", name="ux_manuscripts_report"),
    )

    # 2) manuscript_versions
    op.create_table(
        "manuscript_versions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "manuscript_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("architecture_version", sa.Text(), nullable=False),
        sa.Column("template_version", sa.Text(), nullable=False),
        sa.Column(
            "research_plan_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("research_plan_version", sa.Integer(), nullable=False),
        sa.Column("research_plan_context_hash", sa.Text(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_rationale", sa.Text(), nullable=True),
        sa.Column("abstract_direction", postgresql.JSONB(), nullable=True),
        sa.Column(
            "word_target", sa.Integer(), server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("sections_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("architecture_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("status", MANUSCRIPT_VERSION_STATUSES),
            name="ck_manuscript_versions_status",
        ),
        sa.CheckConstraint(
            "version >= 1", name="ck_manuscript_versions_version",
        ),
        sa.CheckConstraint(
            "word_target >= 0",
            name="ck_manuscript_versions_word_target",
        ),
        sa.UniqueConstraint(
            "manuscript_id", "version",
            name="ux_manuscript_versions_ms_version",
        ),
    )

    # 3) add current_version_id FK after both tables exist
    op.create_foreign_key(
        "fk_manuscripts_current_version",
        "manuscripts", "manuscript_versions",
        ["current_version_id"], ["id"],
        ondelete="SET NULL",
    )

    # 4) manuscript_sections
    op.create_table(
        "manuscript_sections",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_research_plan_section_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_plan_sections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("section_type", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column(
            "required", sa.Boolean(), server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "word_budget", sa.Integer(), server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "budget_weight", sa.Numeric(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "evidence_coverage_target", sa.Numeric(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("research_objective", sa.Text(), nullable=True),
        sa.Column("writing_objective", sa.Text(), nullable=True),
        sa.Column(
            "citation_required", sa.Boolean(),
            server_default=sa.text("false"), nullable=False,
        ),
        sa.Column(
            "research_contract", postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"), nullable=False,
        ),
        sa.Column("section_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint(
            "manuscript_version_id", "section_key",
            name="ux_manuscript_sections_key",
        ),
        sa.UniqueConstraint(
            "manuscript_version_id", "display_order",
            name="ux_manuscript_sections_order",
        ),
        sa.CheckConstraint(
            "display_order >= 0", name="ck_manuscript_sections_order",
        ),
        sa.CheckConstraint(
            "word_budget >= 0", name="ck_manuscript_sections_wb",
        ),
        sa.CheckConstraint(
            "budget_weight >= 0", name="ck_manuscript_sections_bw",
        ),
        sa.CheckConstraint(
            "evidence_coverage_target >= 0 AND "
            "evidence_coverage_target <= 1",
            name="ck_manuscript_sections_ect",
        ),
    )

    # 5) manuscript_section_dependencies
    op.create_table(
        "manuscript_section_dependencies",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "upstream_section_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "downstream_section_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dependency_type", sa.Text(),
            server_default=sa.text("'requires'"), nullable=False,
        ),
        sa.Column("dependency_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("dependency_type", MANUSCRIPT_DEPENDENCY_TYPES),
            name="ck_manuscript_section_dependencies_type",
        ),
        sa.UniqueConstraint(
            "manuscript_version_id",
            "upstream_section_id",
            "downstream_section_id",
            name="ux_manuscript_section_dependencies_edge",
        ),
        sa.CheckConstraint(
            "upstream_section_id <> downstream_section_id",
            name="ck_manuscript_section_dependencies_no_self",
        ),
    )

    # 6) manuscript_runs
    op.create_table(
        "manuscript_runs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
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
            sa.ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("architecture_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
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
            _in_check("status", MANUSCRIPT_RUN_STATUSES),
            name="ck_manuscript_runs_status",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_manuscript_runs_duration",
        ),
    )

    # 7) indexes
    op.create_index("ix_manuscripts_report", "manuscripts", ["report_id"])
    op.create_index("ix_manuscripts_status", "manuscripts", ["status"])
    op.create_index(
        "ix_manuscript_versions_ms_version",
        "manuscript_versions", ["manuscript_id", "version"],
    )
    op.create_index(
        "ix_manuscript_sections_version_order",
        "manuscript_sections",
        ["manuscript_version_id", "display_order"],
    )
    op.create_index(
        "ix_manuscript_section_dependencies_version",
        "manuscript_section_dependencies", ["manuscript_version_id"],
    )
    op.create_index("ix_manuscript_runs_report", "manuscript_runs", ["report_id"])
    op.create_index(
        "ix_manuscript_runs_context", "manuscript_runs",
        ["report_id", "context_hash"],
    )
    op.create_index(
        "ux_manuscript_runs_completed",
        "manuscript_runs",
        ["report_id", "context_hash", "architecture_version"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )


def downgrade() -> None:
    # 1) Drop children first (they reference manuscripts + manuscript_versions)
    op.drop_index("ux_manuscript_runs_completed", table_name="manuscript_runs")
    op.drop_index("ix_manuscript_runs_context", table_name="manuscript_runs")
    op.drop_index("ix_manuscript_runs_report", table_name="manuscript_runs")
    op.drop_table("manuscript_runs")

    op.drop_index(
        "ix_manuscript_section_dependencies_version",
        table_name="manuscript_section_dependencies",
    )
    op.drop_table("manuscript_section_dependencies")

    op.drop_index(
        "ix_manuscript_sections_version_order",
        table_name="manuscript_sections",
    )
    op.drop_table("manuscript_sections")

    # 2) Drop FK from manuscripts -> manuscript_versions
    op.drop_constraint(
        "fk_manuscripts_current_version",
        "manuscripts", type_="foreignkey",
    )
    op.drop_index("ix_manuscripts_status", table_name="manuscripts")
    op.drop_index("ix_manuscripts_report", table_name="manuscripts")

    # 3) Drop manuscript_versions FIRST (its manuscript_id FK to
    #    manuscripts disappears with the table)
    op.drop_index(
        "ix_manuscript_versions_ms_version",
        table_name="manuscript_versions",
    )
    op.drop_table("manuscript_versions")

    # 4) Now manuscripts has no incoming FK references
    op.drop_table("manuscripts")