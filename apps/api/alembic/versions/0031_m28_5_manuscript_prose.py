"""M28.5 — Manuscript prose generation tables.

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-26

Non-destructive: creates four new tables.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


PROSE_GENERATION_MODES = (
    "deterministic", "provider_assisted", "hybrid",
)
PROSE_RUN_STATUSES = (
    "queued", "running", "completed", "partial", "failed", "skipped",
)
PROSE_SECTION_STATUSES = (
    "pending", "running", "completed",
    "insufficient_evidence", "failed", "skipped",
)


def upgrade() -> None:
    # ---- manuscript_prose_runs -------------------------------------
    op.create_table(
        "manuscript_prose_runs",
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
            sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "base_manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "output_manuscript_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "research_plan_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "section_research_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "section_research_runs.id", ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "technical_intelligence_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "technical_intelligence_runs.id", ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "citation_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("citation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("prose_version", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("generation_mode", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "section_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "paragraph_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "sentence_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "word_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column("errors", postgresql.JSONB(), nullable=True),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("output_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("status", PROSE_RUN_STATUSES),
            name="ck_manuscript_prose_runs_status",
        ),
        sa.CheckConstraint(
            _in_check("generation_mode", PROSE_GENERATION_MODES),
            name="ck_manuscript_prose_runs_mode",
        ),
        sa.CheckConstraint(
            "section_count >= 0 AND paragraph_count >= 0 AND "
            "sentence_count >= 0 AND word_count >= 0",
            name="ck_manuscript_prose_runs_counts",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_manuscript_prose_runs_duration",
        ),
    )
    op.create_index(
        "ix_manuscript_prose_runs_project",
        "manuscript_prose_runs", ["project_id"],
    )
    op.create_index(
        "ix_manuscript_prose_runs_report",
        "manuscript_prose_runs", ["report_id"],
    )
    op.create_index(
        "ix_manuscript_prose_runs_context",
        "manuscript_prose_runs",
        ["report_id", "base_manuscript_version_id",
         "context_hash", "prose_version"],
    )
    op.create_index(
        "ux_manuscript_prose_runs_completed",
        "manuscript_prose_runs",
        ["report_id", "base_manuscript_version_id",
         "context_hash", "prose_version"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )

    # ---- manuscript_prose_sections ---------------------------------
    op.create_table(
        "manuscript_prose_sections",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "manuscript_prose_runs.id", ondelete="CASCADE",
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
        sa.Column(
            "manuscript_section_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_sections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("section_type", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "text", sa.Text(),
            server_default=sa.text("''"), nullable=False,
        ),
        sa.Column(
            "char_start", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "char_end", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "word_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "paragraph_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "sentence_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "section_context_hash", sa.Text(),
            server_default=sa.text("''"), nullable=False,
        ),
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("status", PROSE_SECTION_STATUSES),
            name="ck_manuscript_prose_sections_status",
        ),
        sa.CheckConstraint(
            "word_count >= 0 AND paragraph_count >= 0 AND "
            "sentence_count >= 0",
            name="ck_manuscript_prose_sections_counts",
        ),
        sa.UniqueConstraint(
            "run_id", "section_key",
            name="ux_manuscript_prose_sections_run_key",
        ),
    )
    op.create_index(
        "ix_manuscript_prose_sections_run_order",
        "manuscript_prose_sections", ["run_id", "display_order"],
    )
    op.create_index(
        "ix_manuscript_prose_sections_version",
        "manuscript_prose_sections", ["manuscript_version_id"],
    )

    # ---- manuscript_prose_paragraphs --------------------------------
    op.create_table(
        "manuscript_prose_paragraphs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "section_row_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "manuscript_prose_sections.id", ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "manuscript_prose_runs.id", ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column(
            "sentence_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("paragraph_hash", sa.Text(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "ordinal >= 0 AND sentence_count >= 0 AND "
            "char_start >= 0 AND char_end >= char_start",
            name="ck_manuscript_prose_paragraphs_shape",
        ),
        sa.UniqueConstraint(
            "section_row_id", "ordinal",
            name="ux_manuscript_prose_paragraphs_ordinal",
        ),
    )
    op.create_index(
        "ix_manuscript_prose_paragraphs_section",
        "manuscript_prose_paragraphs",
        ["section_row_id", "ordinal"],
    )

    # ---- manuscript_prose_sentences ---------------------------------
    op.create_table(
        "manuscript_prose_sentences",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "paragraph_row_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "manuscript_prose_paragraphs.id", ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "section_row_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "manuscript_prose_sections.id", ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "manuscript_prose_runs.id", ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("global_ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("sentence_hash", sa.Text(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=True),
        sa.Column("citation_refs", postgresql.JSONB(), nullable=True),
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "ordinal >= 0 AND global_ordinal >= 0 AND "
            "char_start >= 0 AND char_end >= char_start",
            name="ck_manuscript_prose_sentences_shape",
        ),
        sa.UniqueConstraint(
            "section_row_id", "global_ordinal",
            name="ux_manuscript_prose_sentences_global_order",
        ),
    )
    op.create_index(
        "ix_manuscript_prose_sentences_paragraph",
        "manuscript_prose_sentences",
        ["paragraph_row_id", "ordinal"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_manuscript_prose_sentences_paragraph",
        table_name="manuscript_prose_sentences",
    )
    op.drop_table("manuscript_prose_sentences")

    op.drop_index(
        "ix_manuscript_prose_paragraphs_section",
        table_name="manuscript_prose_paragraphs",
    )
    op.drop_table("manuscript_prose_paragraphs")

    op.drop_index(
        "ix_manuscript_prose_sections_version",
        table_name="manuscript_prose_sections",
    )
    op.drop_index(
        "ix_manuscript_prose_sections_run_order",
        table_name="manuscript_prose_sections",
    )
    op.drop_table("manuscript_prose_sections")

    op.drop_index(
        "ux_manuscript_prose_runs_completed",
        table_name="manuscript_prose_runs",
    )
    op.drop_index(
        "ix_manuscript_prose_runs_context",
        table_name="manuscript_prose_runs",
    )
    op.drop_index(
        "ix_manuscript_prose_runs_report",
        table_name="manuscript_prose_runs",
    )
    op.drop_index(
        "ix_manuscript_prose_runs_project",
        table_name="manuscript_prose_runs",
    )
    op.drop_table("manuscript_prose_runs")