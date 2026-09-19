"""M19 — ProjectFile ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin


class ProjectFile(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "project_files"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_filename: Mapped[str] = mapped_column(Text, nullable=False)
    extension: Mapped[str | None] = mapped_column(Text, nullable=True)

    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    storage_provider: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)

    client_mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)

    file_kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'uploaded'")
    )
    extraction_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'not_started'")
    )
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_pipeline_version: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Python attr = file_meta; DB column = metadata.
    file_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('uploaded','processing','ready','failed','deleted')",
            name="ck_project_files_status",
        ),
        CheckConstraint(
            "extraction_status IN "
            "('not_started','queued','processing','completed','failed',"
            "'not_supported')",
            name="ck_project_files_extraction_status",
        ),
        CheckConstraint(
            "file_kind IN "
            "('document','pdf','image','archive','text','code',"
            "'structured_data','spreadsheet','presentation','unknown')",
            name="ck_project_files_kind",
        ),
        CheckConstraint(
            "size_bytes >= 0", name="ck_project_files_size_nonneg"
        ),
        CheckConstraint(
            "length(sha256) = 64", name="ck_project_files_sha256_len"
        ),
        CheckConstraint(
            "(status = 'deleted' AND deleted_at IS NOT NULL)"
            " OR "
            "(status <> 'deleted' AND deleted_at IS NULL)",
            name="ck_project_files_deleted_at_consistency",
        ),
        Index(
            "ix_project_files_project_created",
            "project_id",
            "created_at",
        ),
        Index("ix_project_files_project_status", "project_id", "status"),
        Index("ix_project_files_project_kind", "project_id", "file_kind"),
        Index(
            "ux_project_files_project_sha256_active",
            "project_id",
            "sha256",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_project_files_user_created", "uploaded_by", "created_at"),
    )


class ProjectFileEvent(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only audit event for a ProjectFile.

    Immutable by convention: no update/delete service methods exist
    for this table. Mirrors ``ProjectEvent``/``ReportEvent`` naming
    (``event_meta`` Python attr, ``metadata`` DB column).
    """

    __tablename__ = "project_file_events"

    project_file_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_files.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(Text, nullable=False)

    # Python attr = event_meta; DB column = metadata.
    event_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN "
            "('file_uploaded','file_processing_started',"
            "'file_processing_completed','file_processing_failed',"
            "'file_deleted')",
            name="ck_project_file_events_type",
        ),
        Index(
            "ix_project_file_events_file_created",
            "project_file_id",
            "created_at",
        ),
    )
