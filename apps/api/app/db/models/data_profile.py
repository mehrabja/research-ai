"""M20 — Data Intelligence ORM models."""
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


class DataProfile(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "data_profiles"

    project_file_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_files.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    format: Mapped[str] = mapped_column(Text, nullable=False)
    profile_status: Mapped[str] = mapped_column(Text, nullable=False)
    profile_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_version: Mapped[str] = mapped_column(Text, nullable=False)

    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    schema_data: Mapped[dict | None] = mapped_column(
        "schema_json", JSONB, nullable=True
    )
    quality: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    statistics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sample_rows: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "profile_status IN "
            "('pending','completed','failed','unsupported')",
            name="ck_data_profiles_status",
        ),
        CheckConstraint(
            "row_count IS NULL OR row_count >= 0",
            name="ck_data_profiles_rows_nonneg",
        ),
        CheckConstraint(
            "column_count IS NULL OR column_count >= 0",
            name="ck_data_profiles_cols_nonneg",
        ),
        Index("ix_data_profiles_project_file", "project_file_id"),
    )


class DataColumnProfile(Base, UUIDPKMixin, CreatedAtMixin):
    """Child of DataProfile. Ownership derives from parent."""

    __tablename__ = "data_column_profiles"

    data_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("data_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)

    inferred_type: Mapped[str] = mapped_column(Text, nullable=False)
    nullable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    null_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    null_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0.0")
    )

    distinct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unique_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    min_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    median: Mapped[float | None] = mapped_column(Float, nullable=True)
    stddev: Mapped[float | None] = mapped_column(Float, nullable=True)

    top_values: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    column_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "inferred_type IN "
            "('integer','float','boolean','string','datetime','date',"
            "'category','null','mixed','unknown')",
            name="ck_data_column_profiles_type",
        ),
        CheckConstraint(
            "ordinal >= 0", name="ck_data_column_profiles_ordinal"
        ),
        CheckConstraint(
            "null_count >= 0", name="ck_data_column_profiles_nulls"
        ),
        CheckConstraint(
            "null_ratio >= 0.0 AND null_ratio <= 1.0",
            name="ck_data_column_profiles_null_ratio",
        ),
        Index(
            "ix_data_column_profiles_profile_ordinal",
            "data_profile_id",
            "ordinal",
        ),
    )
