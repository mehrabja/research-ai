"""M18-A — Project foundation.

Revision ID: 0011
Revises: 0010
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- projects --------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column(
            "id",
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("research_objective", sa.Text(), nullable=True),
        sa.Column("research_questions", JSONB, nullable=True),
        sa.Column("hypotheses", JSONB, nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_projects_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_projects_user_id_users",
        ),
    )
    op.create_index(
        "ix_projects_user_created", "projects", ["user_id", "created_at"]
    )
    op.create_index("ix_projects_status", "projects", ["status"])

    # --- reports.project_id ----------------------------------------------
    op.add_column(
        "reports",
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_reports_project_id_projects",
        "reports",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_reports_project", "reports", ["project_id"])

    # --- project_events (append-only audit) ------------------------------
    op.create_table(
        "project_events",
        sa.Column(
            "id",
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "event_type IN "
            "('project_created','project_updated','project_archived')",
            name="ck_project_events_type",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="RESTRICT",
            name="fk_project_events_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_project_events_user_id_users",
        ),
    )
    op.create_index(
        "ix_project_events_project_created",
        "project_events",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_events_project_created", table_name="project_events"
    )
    op.drop_table("project_events")

    op.drop_index("ix_reports_project", table_name="reports")
    op.drop_constraint(
        "fk_reports_project_id_projects", "reports", type_="foreignkey"
    )
    op.drop_column("reports", "project_id")

    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_user_created", table_name="projects")
    op.drop_table("projects")