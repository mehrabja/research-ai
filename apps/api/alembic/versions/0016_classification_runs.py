"""M22 — Immutable classification runs (append-only history).

Revision ID: 0016
Revises: 0015
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "classification_runs",
        sa.Column(
            "id", PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column(
            "classification_id", PGUUID(as_uuid=True), nullable=True
        ),
        sa.Column("context_hash", sa.Text(), nullable=True),
        sa.Column("classifier_version", sa.Text(), nullable=False),
        sa.Column("taxonomy_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("domain_code", sa.Text(), nullable=True),
        sa.Column("paper_type_code", sa.Text(), nullable=True),
        sa.Column("research_design_code", sa.Text(), nullable=True),
        sa.Column("confidence_summary", JSONB, nullable=True),
        sa.Column("explanation", JSONB, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            ondelete="CASCADE",
            name="fk_classification_runs_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["classification_id"], ["project_classifications.id"],
            ondelete="SET NULL",
            name="fk_classification_runs_classification_id",
        ),
        sa.CheckConstraint(
            "status IN ('completed','failed','skipped')",
            name="ck_classification_runs_status",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_classification_runs_duration",
        ),
    )

    op.create_index(
        "ix_classification_runs_project_created",
        "classification_runs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_classification_runs_context_hash",
        "classification_runs",
        ["project_id", "context_hash"],
    )

    # Append-only enforcement: block UPDATE. DELETE (for CASCADE
    # and test cleanup) is still allowed.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION classification_runs_no_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'classification_runs is append-only; UPDATE is forbidden';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_classification_runs_no_update
        BEFORE UPDATE ON classification_runs
        FOR EACH ROW EXECUTE FUNCTION classification_runs_no_update();
        """
    )

    # Extend ProjectEvent types to include M22 events.
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


def downgrade() -> None:
    op.drop_constraint(
        "ck_project_events_type", "project_events", type_="check"
    )
    op.create_check_constraint(
        "ck_project_events_type",
        "project_events",
        "event_type IN ("
        "'project_created','project_updated','project_archived',"
        "'classification_recomputed','classification_overridden',"
        "'classification_failed'"
        ")",
    )

    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_classification_runs_no_update ON classification_runs"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS classification_runs_no_update()"
    )

    op.drop_index(
        "ix_classification_runs_context_hash",
        table_name="classification_runs",
    )
    op.drop_index(
        "ix_classification_runs_project_created",
        table_name="classification_runs",
    )
    op.drop_table("classification_runs")