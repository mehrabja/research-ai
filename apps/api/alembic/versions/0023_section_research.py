"""M28 — Section Research tables.

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


RUN_STATUSES = ("running", "completed", "failed", "skipped")


def upgrade() -> None:
    op.create_table(
        "section_research_runs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
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
            sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "manuscript_section_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("contract_hash", sa.Text(), nullable=False),
        sa.Column("m28_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("primary_query", sa.Text(), nullable=False),
        sa.Column("query_plan", postgresql.JSONB(), nullable=False),
        sa.Column("retrieval_config", postgresql.JSONB(), nullable=False),
        sa.Column(
            "retrieval_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("retrieval_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "candidate_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "selected_evidence_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "coverage_score", sa.Numeric(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "coverage_state", sa.Text(),
            server_default=sa.text("'insufficient'"), nullable=False,
        ),
        sa.Column("coverage_summary", postgresql.JSONB(), nullable=True),
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
            name="ck_section_research_runs_status",
        ),
        sa.CheckConstraint(
            "candidate_count >= 0 AND selected_evidence_count >= 0",
            name="ck_section_research_runs_counts",
        ),
        sa.CheckConstraint(
            "coverage_score >= 0 AND coverage_score <= 1",
            name="ck_section_research_runs_coverage",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_section_research_runs_duration",
        ),
    )

    op.create_index(
        "ix_section_research_runs_project",
        "section_research_runs", ["project_id"],
    )
    op.create_index(
        "ix_section_research_runs_section",
        "section_research_runs",
        ["report_id", "manuscript_section_id", "created_at"],
    )
    op.create_index(
        "ix_section_research_runs_context",
        "section_research_runs",
        ["report_id", "manuscript_section_id", "context_hash"],
    )
    op.create_index(
        "ux_section_research_runs_completed",
        "section_research_runs",
        ["report_id", "manuscript_section_id", "context_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )

    op.create_table(
        "section_research_evidence",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "research_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("section_research_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Numeric(), nullable=False),
        sa.Column("retrieval_stage", sa.Text(), nullable=False),
        sa.Column("retrieval_reason", postgresql.JSONB(), nullable=False),
        sa.Column(
            "evidence_role", sa.Text(),
            server_default=sa.text("'support'"), nullable=False,
        ),
        sa.Column(
            "matched_requirement_keys", postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"), nullable=False,
        ),
        sa.Column("citation_label", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("evidence_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "rank >= 1", name="ck_section_research_evidence_rank",
        ),
        sa.CheckConstraint(
            "evidence_role IN ('primary','support')",
            name="ck_section_research_evidence_role",
        ),
        sa.UniqueConstraint(
            "research_run_id", "rank",
            name="ux_section_research_evidence_run_rank",
        ),
    )

    op.create_index(
        "ix_section_research_evidence_run",
        "section_research_evidence",
        ["research_run_id", "rank"],
    )
    op.create_index(
        "ix_section_research_evidence_project_source",
        "section_research_evidence",
        ["project_id", "source_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_section_research_evidence_project_source",
        table_name="section_research_evidence",
    )
    op.drop_index(
        "ix_section_research_evidence_run",
        table_name="section_research_evidence",
    )
    op.drop_table("section_research_evidence")

    op.drop_index(
        "ux_section_research_runs_completed",
        table_name="section_research_runs",
    )
    op.drop_index(
        "ix_section_research_runs_context",
        table_name="section_research_runs",
    )
    op.drop_index(
        "ix_section_research_runs_section",
        table_name="section_research_runs",
    )
    op.drop_index(
        "ix_section_research_runs_project",
        table_name="section_research_runs",
    )
    op.drop_table("section_research_runs")