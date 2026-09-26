"""M18-A — Project ORM models (M37: tenant-aware)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
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


class Project(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # M37 — tenant anchor. Nullable in the DB only between ADD COLUMN
    # and the NOT NULL alter; the ORM always treats it as required.
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)

    research_objective: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    research_questions: Mapped[list[Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    hypotheses: Mapped[list[Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'draft'"),
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    __table_args__ = (
        Index("ix_projects_user_created", "user_id", "created_at"),
        Index("ix_projects_status", "status"),
        Index("ix_projects_workspace", "workspace_id"),
        Index(
            "ix_projects_workspace_status",
            "workspace_id",
            "status",
        ),
    )


class ProjectEvent(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only audit event for a project.

    Immutable by convention: no update/delete service methods exist
    for this table. NOTE: M37 does NOT add workspace_id here; project
    events are always resolved through their parent project.
    """

    __tablename__ = "project_events"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(Text, nullable=False)

    event_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'project_created','project_updated','project_archived',"
            "'classification_started','classification_completed',"
            "'classification_recomputed','classification_overridden',"
            "'classification_failed','classification_skipped',"
            "'literature_analysis_started','literature_analysis_completed',"
            "'literature_analysis_failed','literature_analysis_skipped',"
            "'literature_screening_overridden',"
            "'literature_cluster_completed','literature_gap_detected',"
            "'research_plan_generation_started',"
            "'research_plan_generation_completed',"
            "'research_plan_generation_failed',"
            "'research_plan_generation_skipped',"
            "'knowledge_graph_generation_started',"
            "'knowledge_graph_generation_completed',"
            "'knowledge_graph_generation_failed',"
            "'knowledge_graph_generation_skipped'"
            ")",
            name="ck_project_events_type",
        ),
        Index(
            "ix_project_events_project_created",
            "project_id",
            "created_at",
        ),
    )
