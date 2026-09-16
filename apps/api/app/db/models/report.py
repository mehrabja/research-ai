from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin


REPORT_STATUSES = (
    "draft",
    "searching",
    "extracting",
    "retrieving",
    "generating",
    "review_1",
    "detecting",
    "humanizing",
    "translating",
    "post_translation_review",
    "converging",
    "review_2",
    "validating",
    "completed",
    "failed",
    "cancelled",
)


def _in_check(
    column: str,
    values: tuple[str, ...],
    name: str,
) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class Report(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "reports"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    topic: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    domain: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'draft'"),
    )

    # Free TEXT on purpose: new pipeline phases do not require
    # a CHECK update. Report status itself is CHECK-constrained.
    failed_at_phase: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tone: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    length: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    structure_template: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    output_language: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    audience_level: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        _in_check(
            "status",
            REPORT_STATUSES,
            "ck_reports_status",
        ),
        Index(
            "ix_reports_user_id_created_at",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_reports_status",
            "status",
        ),
    )


class ReportVersion(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "report_versions"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("report_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by_user: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    change_type: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    diff_from_previous: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "version_number",
            "language",
            name="ux_report_versions_report_version_lang",
        ),
        Index(
            "ix_report_versions_report_lang_version",
            "report_id",
            "language",
            "version_number",
        ),
    )


class ReviewEvent(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "review_events"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
    )

    stage: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("report_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        _in_check(
            "stage",
            ("pre_translation", "post_translation"),
            "ck_review_events_stage",
        ),
        _in_check(
            "action",
            (
                "edited",
                "approved",
                "rejected",
                "requested_changes",
            ),
            "ck_review_events_action",
        ),
        Index(
            "ix_review_events_report_created",
            "report_id",
            "created_at",
        ),
    )