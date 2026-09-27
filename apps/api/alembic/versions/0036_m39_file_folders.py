"""M39 F04 — project file folders."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_file_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_file_folders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("project_id", "parent_id", "name", name="ux_project_file_folders_parent_name"),
    )
    op.create_index(
        "ix_project_file_folders_project_parent",
        "project_file_folders",
        ["project_id", "parent_id"],
    )
    op.add_column(
        "project_files",
        sa.Column(
            "folder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_file_folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_project_files_project_folder",
        "project_files",
        ["project_id", "folder_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_files_project_folder", table_name="project_files")
    op.drop_column("project_files", "folder_id")
    op.drop_index("ix_project_file_folders_project_parent", table_name="project_file_folders")
    op.drop_table("project_file_folders")
