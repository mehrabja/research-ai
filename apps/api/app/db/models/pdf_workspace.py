from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class PdfWorkspaceState(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "pdf_workspace_states"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    active_file_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    page_number: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    zoom: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )
    scroll_x: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    scroll_y: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    workspace_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "page_number >= 1", name="ck_pdf_workspace_page_pos"
        ),
        CheckConstraint(
            "zoom >= 0.25 AND zoom <= 4.0",
            name="ck_pdf_workspace_zoom_range",
        ),
        CheckConstraint(
            "scroll_x >= 0", name="ck_pdf_workspace_scroll_x_nonneg"
        ),
        CheckConstraint(
            "scroll_y >= 0", name="ck_pdf_workspace_scroll_y_nonneg"
        ),
        Index(
            "ix_pdf_workspace_states_project",
            "project_id",
        ),
    )


class PdfAnnotation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "pdf_annotations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rect: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    annotation_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('highlight','note')",
            name="ck_pdf_annotations_kind",
        ),
        CheckConstraint(
            "page_number >= 1",
            name="ck_pdf_annotations_page_pos",
        ),
        Index(
            "ix_pdf_annotations_project_file_page",
            "project_id",
            "file_id",
            "page_number",
        ),
    )
