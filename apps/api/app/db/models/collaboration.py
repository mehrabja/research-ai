"""M34 — Collaboration / versioning / review workspace ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin
from app.domain.collaboration import (
    COLLABORATION_EVENT_TYPES,
    COMMENT_STATUSES,
    PROJECT_ROLES,
    REVIEW_SEVERITIES,
    REVIEW_TASK_STATUSES,
)


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class ProjectMember(Base, UUIDPKMixin, TimestampMixin):
    """Explicit project membership row.

    The project owner is NOT required to have a row here; ownership is
    derived from ``projects.user_id``. All other collaborators must be
    listed here.
    """

    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        _in_check("role", PROJECT_ROLES, "ck_project_members_role"),
        UniqueConstraint(
            "project_id", "user_id",
            name="ux_project_members_project_user",
        ),
        Index("ix_project_members_project", "project_id"),
        Index("ix_project_members_user", "user_id"),
    )


class ManuscriptBranch(Base, UUIDPKMixin, TimestampMixin):
    """Named workstream pointing to an immutable ManuscriptVersion."""

    __tablename__ = "manuscript_branches"

    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscripts.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    head_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    branch_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(name) > 0",
            name="ck_manuscript_branches_name",
        ),
        UniqueConstraint(
            "manuscript_id", "name",
            name="ux_manuscript_branches_ms_name",
        ),
        Index(
            "ux_manuscript_branches_default",
            "manuscript_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        Index(
            "ix_manuscript_branches_ms", "manuscript_id",
        ),
    )


class ManuscriptComment(Base, UUIDPKMixin, TimestampMixin):
    """Version-aware comment. Anchored to a specific manuscript version."""

    __tablename__ = "manuscript_comments"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_section_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_comments.id", ondelete="CASCADE"),
        nullable=True,
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'open'")
    )
    anchor: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check(
            "status", COMMENT_STATUSES, "ck_manuscript_comments_status",
        ),
        Index(
            "ix_manuscript_comments_version",
            "manuscript_version_id", "created_at",
        ),
        Index(
            "ix_manuscript_comments_status", "status",
        ),
        Index(
            "ix_manuscript_comments_project", "project_id",
        ),
    )


class ManuscriptReviewTask(Base, UUIDPKMixin, TimestampMixin):
    """A structured review request."""

    __tablename__ = "manuscript_review_tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    manuscript_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    severity: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'info'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'open'")
    )
    related_section_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("manuscript_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_qa_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("academic_qa_findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_citation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("citation_identities.id", ondelete="SET NULL"),
        nullable=True,
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        _in_check(
            "severity", REVIEW_SEVERITIES,
            "ck_manuscript_review_tasks_severity",
        ),
        _in_check(
            "status", REVIEW_TASK_STATUSES,
            "ck_manuscript_review_tasks_status",
        ),
        Index(
            "ix_manuscript_review_tasks_version",
            "manuscript_version_id", "created_at",
        ),
        Index(
            "ix_manuscript_review_tasks_status", "status",
        ),
        Index(
            "ix_manuscript_review_tasks_assignee",
            "assignee_user_id", "status",
        ),
    )


class ProjectCollaborationEvent(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only audit trail for collaboration mutations (project-scoped)."""

    __tablename__ = "project_collaboration_events"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    event_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        _in_check(
            "event_type", COLLABORATION_EVENT_TYPES,
            "ck_project_collaboration_events_type",
        ),
        Index(
            "ix_project_collaboration_events_project_created",
            "project_id", "created_at",
        ),
    )
