"""M34 — Collaboration / versioning / review workspace.

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-25

Non-destructive:
  - adds one nullable FK column to manuscript_versions
  - creates five new tables
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


PROJECT_ROLES = ("owner", "editor", "reviewer", "viewer")
COMMENT_STATUSES = ("open", "resolved", "reopened")
REVIEW_TASK_STATUSES = (
    "open", "in_progress", "blocked", "resolved", "rejected",
)
REVIEW_SEVERITIES = ("info", "warning", "error", "blocking")
COLLABORATION_EVENT_TYPES = (
    "member_added", "member_removed", "role_changed",
    "version_created", "branch_created", "branch_merged",
    "comment_created", "comment_resolved", "comment_reopened",
    "review_task_created", "review_task_status_changed",
    "review_task_resolved",
)


def upgrade() -> None:
    # --- manuscript_versions: add parent_version_id (nullable) ---
    op.add_column(
        "manuscript_versions",
        sa.Column(
            "parent_version_id", postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_manuscript_versions_parent",
        "manuscript_versions",
        "manuscript_versions",
        ["parent_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- project_members ---
    op.create_table(
        "project_members",
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
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "added_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
            _in_check("role", PROJECT_ROLES),
            name="ck_project_members_role",
        ),
        sa.UniqueConstraint(
            "project_id", "user_id",
            name="ux_project_members_project_user",
        ),
    )
    op.create_index(
        "ix_project_members_project", "project_members", ["project_id"],
    )
    op.create_index(
        "ix_project_members_user", "project_members", ["user_id"],
    )

    # --- manuscript_branches ---
    op.create_table(
        "manuscript_branches",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "manuscript_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "head_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "manuscript_versions.id", ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "is_default", sa.Boolean(),
            server_default=sa.text("false"), nullable=False,
        ),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("branch_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(name) > 0",
            name="ck_manuscript_branches_name",
        ),
        sa.UniqueConstraint(
            "manuscript_id", "name",
            name="ux_manuscript_branches_ms_name",
        ),
    )
    op.create_index(
        "ux_manuscript_branches_default",
        "manuscript_branches",
        ["manuscript_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )
    op.create_index(
        "ix_manuscript_branches_ms",
        "manuscript_branches",
        ["manuscript_id"],
    )

    # --- manuscript_comments ---
    op.create_table(
        "manuscript_comments",
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
            "parent_comment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "author_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'open'"), nullable=False,
        ),
        sa.Column("anchor", postgresql.JSONB(), nullable=True),
        sa.Column(
            "resolved_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resolved_at", sa.DateTime(timezone=True), nullable=True,
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
            _in_check("status", COMMENT_STATUSES),
            name="ck_manuscript_comments_status",
        ),
    )
    op.create_index(
        "ix_manuscript_comments_version",
        "manuscript_comments",
        ["manuscript_version_id", "created_at"],
    )
    op.create_index(
        "ix_manuscript_comments_status",
        "manuscript_comments", ["status"],
    )
    op.create_index(
        "ix_manuscript_comments_project",
        "manuscript_comments", ["project_id"],
    )

    # --- manuscript_review_tasks ---
    op.create_table(
        "manuscript_review_tasks",
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
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assignee_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope", postgresql.JSONB(), nullable=True),
        sa.Column(
            "severity", sa.Text(),
            server_default=sa.text("'info'"), nullable=False,
        ),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'open'"), nullable=False,
        ),
        sa.Column(
            "related_section_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_sections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "related_qa_finding_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic_qa_findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "related_citation_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "citation_identities.id", ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", postgresql.JSONB(), nullable=True),
        sa.Column(
            "resolved_at", sa.DateTime(timezone=True), nullable=True,
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
            _in_check("severity", REVIEW_SEVERITIES),
            name="ck_manuscript_review_tasks_severity",
        ),
        sa.CheckConstraint(
            _in_check("status", REVIEW_TASK_STATUSES),
            name="ck_manuscript_review_tasks_status",
        ),
    )
    op.create_index(
        "ix_manuscript_review_tasks_version",
        "manuscript_review_tasks",
        ["manuscript_version_id", "created_at"],
    )
    op.create_index(
        "ix_manuscript_review_tasks_status",
        "manuscript_review_tasks", ["status"],
    )
    op.create_index(
        "ix_manuscript_review_tasks_assignee",
        "manuscript_review_tasks", ["assignee_user_id", "status"],
    )

    # --- project_collaboration_events ---
    op.create_table(
        "project_collaboration_events",
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
            "actor_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column(
            "target_id", postgresql.UUID(as_uuid=True), nullable=True,
        ),
        sa.Column("event_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("event_type", COLLABORATION_EVENT_TYPES),
            name="ck_project_collaboration_events_type",
        ),
    )
    op.create_index(
        "ix_project_collaboration_events_project_created",
        "project_collaboration_events",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_collaboration_events_project_created",
        table_name="project_collaboration_events",
    )
    op.drop_table("project_collaboration_events")

    op.drop_index(
        "ix_manuscript_review_tasks_assignee",
        table_name="manuscript_review_tasks",
    )
    op.drop_index(
        "ix_manuscript_review_tasks_status",
        table_name="manuscript_review_tasks",
    )
    op.drop_index(
        "ix_manuscript_review_tasks_version",
        table_name="manuscript_review_tasks",
    )
    op.drop_table("manuscript_review_tasks")

    op.drop_index(
        "ix_manuscript_comments_project",
        table_name="manuscript_comments",
    )
    op.drop_index(
        "ix_manuscript_comments_status",
        table_name="manuscript_comments",
    )
    op.drop_index(
        "ix_manuscript_comments_version",
        table_name="manuscript_comments",
    )
    op.drop_table("manuscript_comments")

    op.drop_index(
        "ix_manuscript_branches_ms",
        table_name="manuscript_branches",
    )
    op.drop_index(
        "ux_manuscript_branches_default",
        table_name="manuscript_branches",
    )
    op.drop_table("manuscript_branches")

    op.drop_index(
        "ix_project_members_user", table_name="project_members",
    )
    op.drop_index(
        "ix_project_members_project", table_name="project_members",
    )
    op.drop_table("project_members")

    op.drop_constraint(
        "fk_manuscript_versions_parent",
        "manuscript_versions",
        type_="foreignkey",
    )
    op.drop_column("manuscript_versions", "parent_version_id")