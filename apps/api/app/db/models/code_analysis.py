"""M20 — Code Intelligence ORM models."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin


class CodeAnalysis(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "code_analyses"

    project_file_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_files.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    language: Mapped[str] = mapped_column(Text, nullable=False)
    language_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_version: Mapped[str] = mapped_column(Text, nullable=False)

    parse_status: Mapped[str] = mapped_column(Text, nullable=False)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    line_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    character_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    symbol_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    function_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    class_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    import_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    complexity_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    analysis_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "parse_status IN ('pending','completed','failed','unsupported')",
            name="ck_code_analyses_status",
        ),
        CheckConstraint(
            "line_count >= 0", name="ck_code_analyses_lines_nonneg"
        ),
        CheckConstraint(
            "character_count >= 0",
            name="ck_code_analyses_chars_nonneg",
        ),
        CheckConstraint(
            "symbol_count >= 0", name="ck_code_analyses_symbols_nonneg"
        ),
        Index(
            "ix_code_analyses_project_file",
            "project_file_id",
        ),
    )


class CodeSymbol(Base, UUIDPKMixin, CreatedAtMixin):
    """Child of CodeAnalysis. Ownership derives from parent; no
    duplicate project_file_id column — the FK already encodes it."""

    __tablename__ = "code_symbols"

    code_analysis_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("code_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )

    symbol_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    column_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)

    symbol_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "symbol_type IN "
            "('module','class','function','method','variable','constant',"
            "'import')",
            name="ck_code_symbols_type",
        ),
        CheckConstraint(
            "line_start >= 1", name="ck_code_symbols_line_start"
        ),
        CheckConstraint(
            "line_end >= line_start", name="ck_code_symbols_line_range"
        ),
        Index(
            "ix_code_symbols_analysis_type",
            "code_analysis_id",
            "symbol_type",
        ),
        Index("ix_code_symbols_name", "name"),
    )


class CodeDependency(Base, UUIDPKMixin, CreatedAtMixin):
    """Child of CodeAnalysis. Ownership derives from parent."""

    __tablename__ = "code_dependencies"

    code_analysis_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("code_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )

    dependency_name: Mapped[str] = mapped_column(Text, nullable=False)
    dependency_type: Mapped[str] = mapped_column(Text, nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_relative: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    dependency_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "dependency_type IN "
            "('import','from_import','require','include','package','unknown')",
            name="ck_code_dependencies_type",
        ),
        Index(
            "ix_code_dependencies_analysis",
            "code_analysis_id",
        ),
        Index(
            "ix_code_dependencies_name",
            "dependency_name",
        ),
    )
