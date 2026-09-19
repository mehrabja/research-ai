"""M19 — Universal File Intelligence foundation.

Revision ID: 0012
Revises: 0011
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_files",
        sa.Column(
            "id",
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", PGUUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("normalized_filename", sa.Text(), nullable=False),
        sa.Column("extension", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("storage_provider", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("client_mime_type", sa.Text(), nullable=True),
        sa.Column("detected_mime_type", sa.Text(), nullable=True),
        sa.Column("file_kind", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'uploaded'"),
        ),
        sa.Column(
            "extraction_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'not_started'"),
        ),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "extraction_pipeline_version", sa.Text(), nullable=True
        ),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN "
            "('uploaded','processing','ready','failed','deleted')",
            name="ck_project_files_status",
        ),
        sa.CheckConstraint(
            "extraction_status IN "
            "('not_started','queued','processing','completed','failed',"
            "'not_supported')",
            name="ck_project_files_extraction_status",
        ),
        sa.CheckConstraint(
            "file_kind IN "
            "('document','pdf','image','archive','text','code',"
            "'structured_data','spreadsheet','presentation','unknown')",
            name="ck_project_files_kind",
        ),
        sa.CheckConstraint(
            "size_bytes >= 0", name="ck_project_files_size_nonneg"
        ),
        sa.CheckConstraint(
            "length(sha256) = 64", name="ck_project_files_sha256_len"
        ),
        sa.CheckConstraint(
            "(status = 'deleted' AND deleted_at IS NOT NULL)"
            " OR "
            "(status <> 'deleted' AND deleted_at IS NULL)",
            name="ck_project_files_deleted_at_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="fk_project_files_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_project_files_uploaded_by_users",
        ),
    )
    op.create_index(
        "ix_project_files_project_created",
        "project_files",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_project_files_project_status",
        "project_files",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_project_files_project_kind",
        "project_files",
        ["project_id", "file_kind"],
    )
    op.create_index(
        "ix_project_files_user_created",
        "project_files",
        ["uploaded_by", "created_at"],
    )
    op.create_index(
        "ux_project_files_project_sha256_active",
        "project_files",
        ["project_id", "sha256"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "project_file_events",
        sa.Column(
            "id",
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_file_id", PGUUID(as_uuid=True), nullable=False),
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
            "('file_uploaded','file_processing_started',"
            "'file_processing_completed','file_processing_failed',"
            "'file_deleted')",
            name="ck_project_file_events_type",
        ),
        sa.ForeignKeyConstraint(
            ["project_file_id"],
            ["project_files.id"],
            ondelete="RESTRICT",
            name="fk_project_file_events_file_id_project_files",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_project_file_events_user_id_users",
        ),
    )
    op.create_index(
        "ix_project_file_events_file_created",
        "project_file_events",
        ["project_file_id", "created_at"],
    )

    op.add_column(
        "jobs",
        sa.Column("project_file_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_jobs_project_file_id_project_files",
        "jobs",
        "project_files",
        ["project_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_jobs_project_file", "jobs", ["project_file_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_project_file", table_name="jobs")
    op.drop_constraint(
        "fk_jobs_project_file_id_project_files", "jobs", type_="foreignkey"
    )
    op.drop_column("jobs", "project_file_id")

    op.drop_index(
        "ix_project_file_events_file_created",
        table_name="project_file_events",
    )
    op.drop_table("project_file_events")

    op.drop_index(
        "ux_project_files_project_sha256_active",
        table_name="project_files",
    )
    op.drop_index(
        "ix_project_files_user_created", table_name="project_files"
    )
    op.drop_index(
        "ix_project_files_project_kind", table_name="project_files"
    )
    op.drop_index(
        "ix_project_files_project_status", table_name="project_files"
    )
    op.drop_index(
        "ix_project_files_project_created", table_name="project_files"
    )
    op.drop_table("project_files")