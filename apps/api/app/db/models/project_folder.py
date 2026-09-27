from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class ProjectFolder(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "project_folders"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_folders.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "parent_id",
            "name",
            name="ux_project_folders_project_parent_name",
        ),
        Index(
            "ix_project_folders_project_parent",
            "project_id",
            "parent_id",
            "name",
        ),
    )
