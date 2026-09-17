from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin


def _in_check(
    column: str,
    values: tuple[str, ...],
    name: str,
) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class GenerationRun(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "generation_runs"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
    )
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_token_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    output_token_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    output_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check(
            "status",
            ("pending", "running", "success", "failed", "cancelled"),
            "ck_generation_runs_status",
        ),
        CheckConstraint(
            "input_token_count IS NULL OR input_token_count >= 0",
            name="ck_generation_runs_input_tokens",
        ),
        CheckConstraint(
            "output_token_count IS NULL OR output_token_count >= 0",
            name="ck_generation_runs_output_tokens",
        ),
        Index(
            "ix_generation_runs_report_created",
            "report_id",
            "created_at",
        ),
    )


class DetectionRun(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "detection_runs"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
    )

    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("generation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # M13 identity columns.
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("report_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    profile_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scanned_text_version: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    overall_score: Mapped[Decimal | None] = mapped_column(
        Numeric, nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    detection_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        _in_check(
            "status",
            ("pending", "running", "completed", "failed"),
            "ck_detection_runs_status",
        ),
        CheckConstraint(
            "input_chars IS NULL OR input_chars >= 0",
            name="ck_detection_runs_input_chars",
        ),
        Index(
            "ix_detection_runs_report_created",
            "report_id",
            "created_at",
        ),
        Index(
            "ux_detection_runs_identity",
            "report_id",
            "version_id",
            "profile_id",
            "input_hash",
            unique=True,
            postgresql_where=text("status = 'completed'"),
        ),
    )


class DetectionSegment(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "detection_segments"

    detection_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("detection_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    paragraph_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    segment_identifier: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    flagged: Mapped[bool | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    segment_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "paragraph_index IS NULL OR paragraph_index >= 0",
            name="ck_detection_segments_paragraph_index",
        ),
        Index("ix_detection_segments_run", "detection_run_id"),
    )


class TranslationRun(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "translation_runs"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
    )
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("generation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("report_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    profile_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_lang: Mapped[str] = mapped_column(Text, nullable=False)
    target_lang: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check(
            "status",
            ("pending", "running", "success", "partial", "failed"),
            "ck_translation_runs_status",
        ),
        Index(
            "ix_translation_runs_report_created",
            "report_id",
            "created_at",
        ),
    )


class TranslationVersion(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "translation_versions"

    translation_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("translation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    preservation_check_status: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    preservation_details: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        Index("ix_translation_versions_run", "translation_run_id"),
    )
