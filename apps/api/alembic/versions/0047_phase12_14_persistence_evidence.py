"""Unified legacy Phase 12-14 persistence and evidence bridge.

Revision ID: 0047
Revises: 0046
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pdf_workspace_states",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "active_file_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("page_number", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("zoom", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("scroll_x", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("scroll_y", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["active_file_id"], ["project_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
        sa.CheckConstraint("page_number >= 1", name="ck_pdf_workspace_page_pos"),
        sa.CheckConstraint(
            "zoom >= 0.25 AND zoom <= 4.0",
            name="ck_pdf_workspace_zoom_range",
        ),
        sa.CheckConstraint("scroll_x >= 0", name="ck_pdf_workspace_scroll_x_nonneg"),
        sa.CheckConstraint("scroll_y >= 0", name="ck_pdf_workspace_scroll_y_nonneg"),
    )
    op.create_index(
        "ix_pdf_workspace_states_project",
        "pdf_workspace_states",
        ["project_id"],
    )

    op.create_table(
        "pdf_annotations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("selected_text", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("rect", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["project_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('highlight','note')", name="ck_pdf_annotations_kind"),
        sa.CheckConstraint("page_number >= 1", name="ck_pdf_annotations_page_pos"),
    )
    op.create_index(
        "ix_pdf_annotations_project_file_page",
        "pdf_annotations",
        ["project_id", "file_id", "page_number"],
    )

    op.create_table(
        "research_canvases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "nodes",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "edges",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "viewport",
            postgresql.JSONB(),
            server_default=sa.text("'{\"x\":0,\"y\":0,\"zoom\":1}'::jsonb"),
            nullable=False,
        ),
        sa.Column("updated_by_user", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
        sa.CheckConstraint("revision >= 1", name="ck_research_canvases_revision_pos"),
    )
    op.create_index(
        "ix_research_canvases_project",
        "research_canvases",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_canvases_project", table_name="research_canvases")
    op.drop_table("research_canvases")
    op.drop_index(
        "ix_pdf_annotations_project_file_page",
        table_name="pdf_annotations",
    )
    op.drop_table("pdf_annotations")
    op.drop_index(
        "ix_pdf_workspace_states_project",
        table_name="pdf_workspace_states",
    )
    op.drop_table("pdf_workspace_states")
