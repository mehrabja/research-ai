"""M39 project file folders."""
from __future__ import annotations
import uuid
from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPKMixin
class FileFolder(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "file_folders"
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    parent_folder_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("file_folders.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    __table_args__ = (Index("ix_file_folders_project_parent", "project_id", "parent_folder_id"),
        UniqueConstraint("project_id", "parent_folder_id", "name", name="ux_file_folders_project_parent_name"))
