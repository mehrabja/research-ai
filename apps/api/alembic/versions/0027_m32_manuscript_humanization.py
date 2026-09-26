"""M32 — Manuscript humanization extensions to M14.

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-25

Non-destructive:
  - adds nullable columns to humanization_runs / humanization_iterations
  - widens stage CHECK to allow 'manuscript'
  - does not modify any existing row semantics
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- humanization_runs: new nullable columns ---
    op.add_column(
        "humanization_runs",
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "humanization_runs",
        sa.Column(
            "manuscript_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscripts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "humanization_runs",
        sa.Column("mode", sa.Text(), nullable=True),
    )
    op.add_column(
        "humanization_runs",
        sa.Column("m32_version", sa.Text(), nullable=True),
    )
    op.add_column(
        "humanization_runs",
        sa.Column("context_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "humanization_runs",
        sa.Column("gate", sa.Text(), nullable=True),
    )
    op.add_column(
        "humanization_runs",
        sa.Column("preservation_summary", postgresql.JSONB(), nullable=True),
    )

    # --- widen stage CHECK to allow 'manuscript' ---
    op.drop_constraint(
        "ck_humanization_runs_stage", "humanization_runs", type_="check",
    )
    op.create_check_constraint(
        "ck_humanization_runs_stage",
        "humanization_runs",
        "stage IN ('pre_translation','post_translation','manuscript')",
    )

    # --- new CHECKs for M32 fields ---
    op.create_check_constraint(
        "ck_humanization_runs_mode",
        "humanization_runs",
        "mode IS NULL OR mode IN "
        "('conservative','academic','natural_academic','journal_targeted')",
    )
    op.create_check_constraint(
        "ck_humanization_runs_gate",
        "humanization_runs",
        "gate IS NULL OR gate IN ('pass','pass_with_warnings','rejected')",
    )

    # --- indexes ---
    op.create_index(
        "ix_humanization_runs_mv",
        "humanization_runs",
        ["manuscript_version_id"],
        postgresql_where=sa.text("manuscript_version_id IS NOT NULL"),
    )
    op.create_index(
        "ux_humanization_runs_m32_completed",
        "humanization_runs",
        ["manuscript_version_id", "context_hash",
         "m32_version", "mode"],
        unique=True,
        postgresql_where=sa.text(
            "stage = 'manuscript' AND status = 'success' "
            "AND manuscript_version_id IS NOT NULL"
        ),
    )

    # --- humanization_iterations: new nullable columns ---
    op.add_column(
        "humanization_iterations",
        sa.Column("preservation_result", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "humanization_iterations",
        sa.Column("qa_impact", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "humanization_iterations",
        sa.Column("accepted", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("humanization_iterations", "accepted")
    op.drop_column("humanization_iterations", "qa_impact")
    op.drop_column("humanization_iterations", "preservation_result")

    op.drop_index(
        "ux_humanization_runs_m32_completed",
        table_name="humanization_runs",
    )
    op.drop_index(
        "ix_humanization_runs_mv", table_name="humanization_runs",
    )

    op.drop_constraint(
        "ck_humanization_runs_gate", "humanization_runs", type_="check",
    )
    op.drop_constraint(
        "ck_humanization_runs_mode", "humanization_runs", type_="check",
    )

    op.drop_constraint(
        "ck_humanization_runs_stage", "humanization_runs", type_="check",
    )
    op.create_check_constraint(
        "ck_humanization_runs_stage",
        "humanization_runs",
        "stage IN ('pre_translation','post_translation')",
    )

    op.drop_column("humanization_runs", "preservation_summary")
    op.drop_column("humanization_runs", "gate")
    op.drop_column("humanization_runs", "context_hash")
    op.drop_column("humanization_runs", "m32_version")
    op.drop_column("humanization_runs", "mode")
    op.drop_column("humanization_runs", "manuscript_id")
    op.drop_column("humanization_runs", "manuscript_version_id")