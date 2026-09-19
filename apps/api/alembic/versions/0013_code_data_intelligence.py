"""M20 — Code & Data Intelligence.

Revision ID: 0013
Revises: 0012
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- code_analyses ---------------------------------------------------
    op.create_table(
        "code_analyses",
        sa.Column(
            "id", PGUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_file_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("language_version", sa.Text(), nullable=True),
        sa.Column("parser", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("analysis_version", sa.Text(), nullable=False),
        sa.Column("parse_status", sa.Text(), nullable=False),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column(
            "line_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "character_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "symbol_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "function_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "class_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "import_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("complexity_score", sa.Float(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "parse_status IN "
            "('pending','completed','failed','unsupported')",
            name="ck_code_analyses_status",
        ),
        sa.CheckConstraint(
            "line_count >= 0", name="ck_code_analyses_lines_nonneg"
        ),
        sa.CheckConstraint(
            "character_count >= 0", name="ck_code_analyses_chars_nonneg"
        ),
        sa.CheckConstraint(
            "symbol_count >= 0",
            name="ck_code_analyses_symbols_nonneg",
        ),
        sa.ForeignKeyConstraint(
            ["project_file_id"],
            ["project_files.id"],
            ondelete="CASCADE",
            name="fk_code_analyses_project_file_id_project_files",
        ),
        sa.UniqueConstraint(
            "project_file_id",
            name="ux_code_analyses_project_file",
        ),
    )
    op.create_index(
        "ix_code_analyses_project_file",
        "code_analyses",
        ["project_file_id"],
    )

    # --- code_symbols ----------------------------------------------------
    op.create_table(
        "code_symbols",
        sa.Column(
            "id", PGUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code_analysis_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("symbol_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("parent_name", sa.Text(), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("column_start", sa.Integer(), nullable=True),
        sa.Column("column_end", sa.Integer(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "symbol_type IN "
            "('module','class','function','method','variable','constant',"
            "'import')",
            name="ck_code_symbols_type",
        ),
        sa.CheckConstraint(
            "line_start >= 1", name="ck_code_symbols_line_start"
        ),
        sa.CheckConstraint(
            "line_end >= line_start", name="ck_code_symbols_line_range"
        ),
        sa.ForeignKeyConstraint(
            ["code_analysis_id"],
            ["code_analyses.id"],
            ondelete="CASCADE",
            name="fk_code_symbols_code_analysis_id_code_analyses",
        ),
    )
    op.create_index(
        "ix_code_symbols_analysis_type",
        "code_symbols",
        ["code_analysis_id", "symbol_type"],
    )
    op.create_index("ix_code_symbols_name", "code_symbols", ["name"])

    # --- code_dependencies ----------------------------------------------
    op.create_table(
        "code_dependencies",
        sa.Column(
            "id", PGUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code_analysis_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("dependency_name", sa.Text(), nullable=False),
        sa.Column("dependency_type", sa.Text(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column(
            "is_relative", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "dependency_type IN "
            "('import','from_import','require','include','package','unknown')",
            name="ck_code_dependencies_type",
        ),
        sa.ForeignKeyConstraint(
            ["code_analysis_id"],
            ["code_analyses.id"],
            ondelete="CASCADE",
            name="fk_code_dependencies_code_analysis_id_code_analyses",
        ),
    )
    op.create_index(
        "ix_code_dependencies_analysis",
        "code_dependencies",
        ["code_analysis_id"],
    )
    op.create_index(
        "ix_code_dependencies_name",
        "code_dependencies",
        ["dependency_name"],
    )

    # --- data_profiles ---------------------------------------------------
    op.create_table(
        "data_profiles",
        sa.Column(
            "id", PGUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_file_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("profile_status", sa.Text(), nullable=False),
        sa.Column("profile_error", sa.Text(), nullable=True),
        sa.Column("profile_version", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("column_count", sa.Integer(), nullable=True),
        sa.Column("schema_json", JSONB, nullable=True),
        sa.Column("quality", JSONB, nullable=True),
        sa.Column("statistics", JSONB, nullable=True),
        sa.Column("sample_rows", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "profile_status IN "
            "('pending','completed','failed','unsupported')",
            name="ck_data_profiles_status",
        ),
        sa.CheckConstraint(
            "row_count IS NULL OR row_count >= 0",
            name="ck_data_profiles_rows_nonneg",
        ),
        sa.CheckConstraint(
            "column_count IS NULL OR column_count >= 0",
            name="ck_data_profiles_cols_nonneg",
        ),
        sa.ForeignKeyConstraint(
            ["project_file_id"],
            ["project_files.id"],
            ondelete="CASCADE",
            name="fk_data_profiles_project_file_id_project_files",
        ),
        sa.UniqueConstraint(
            "project_file_id",
            name="ux_data_profiles_project_file",
        ),
    )
    op.create_index(
        "ix_data_profiles_project_file",
        "data_profiles",
        ["project_file_id"],
    )

    # --- data_column_profiles --------------------------------------------
    op.create_table(
        "data_column_profiles",
        sa.Column(
            "id", PGUUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("data_profile_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("inferred_type", sa.Text(), nullable=False),
        sa.Column(
            "nullable", sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "null_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "null_ratio", sa.Float(), nullable=False,
            server_default=sa.text("0.0"),
        ),
        sa.Column("distinct_count", sa.Integer(), nullable=True),
        sa.Column("unique_ratio", sa.Float(), nullable=True),
        sa.Column("min_value", sa.Text(), nullable=True),
        sa.Column("max_value", sa.Text(), nullable=True),
        sa.Column("mean", sa.Float(), nullable=True),
        sa.Column("median", sa.Float(), nullable=True),
        sa.Column("stddev", sa.Float(), nullable=True),
        sa.Column("top_values", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "inferred_type IN "
            "('integer','float','boolean','string','datetime','date',"
            "'category','null','mixed','unknown')",
            name="ck_data_column_profiles_type",
        ),
        sa.CheckConstraint(
            "ordinal >= 0", name="ck_data_column_profiles_ordinal"
        ),
        sa.CheckConstraint(
            "null_count >= 0", name="ck_data_column_profiles_nulls"
        ),
        sa.CheckConstraint(
            "null_ratio >= 0.0 AND null_ratio <= 1.0",
            name="ck_data_column_profiles_null_ratio",
        ),
        sa.ForeignKeyConstraint(
            ["data_profile_id"],
            ["data_profiles.id"],
            ondelete="CASCADE",
            name="fk_data_column_profiles_data_profile_id_data_profiles",
        ),
    )
    op.create_index(
        "ix_data_column_profiles_profile_ordinal",
        "data_column_profiles",
        ["data_profile_id", "ordinal"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_column_profiles_profile_ordinal",
        table_name="data_column_profiles",
    )
    op.drop_table("data_column_profiles")

    op.drop_index(
        "ix_data_profiles_project_file", table_name="data_profiles"
    )
    op.drop_table("data_profiles")

    op.drop_index(
        "ix_code_dependencies_name", table_name="code_dependencies"
    )
    op.drop_index(
        "ix_code_dependencies_analysis", table_name="code_dependencies"
    )
    op.drop_table("code_dependencies")

    op.drop_index("ix_code_symbols_name", table_name="code_symbols")
    op.drop_index(
        "ix_code_symbols_analysis_type", table_name="code_symbols"
    )
    op.drop_table("code_symbols")

    op.drop_index(
        "ix_code_analyses_project_file", table_name="code_analyses"
    )
    op.drop_table("code_analyses")