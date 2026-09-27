"""F04 — project folders.

Revision ID: 0035
Revises: 0034
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_folders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "parent_id", "name", name="ux_project_folders_project_parent_name"),
    )
    op.create_index("ix_project_folders_project_parent", "project_folders", ["project_id", "parent_id", "name"])

    op.add_column("project_files", sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_project_files_folder", "project_files", "project_folders", ["folder_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_project_files_folder", "project_files", ["project_id", "folder_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_project_files_folder", table_name="project_files")
    op.drop_constraint("fk_project_files_folder", "project_files", type_="foreignkey")
    op.drop_column("project_files", "folder_id")
    op.drop_index("ix_project_folders_project_parent", table_name="project_folders")
    op.drop_table("project_folders")
