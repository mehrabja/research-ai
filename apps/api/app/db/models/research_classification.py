"""M21 — Classification ORM models (aggregate + evidence)."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin


class ProjectClassification(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "project_classifications"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_domains.id", ondelete="SET NULL"),
        nullable=True,
    )
    domain_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    domain_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain_alternatives: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )

    paper_type_code: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey(
            "paper_types.code",
            ondelete="SET NULL",
            name="fk_project_classifications_paper_type_code",
        ),
        nullable=True,
    )
    paper_type_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    paper_type_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    paper_type_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    paper_type_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paper_type_alternatives: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    paper_type_secondary: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )

    research_design_code: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey(
            "research_designs.code",
            ondelete="SET NULL",
            name="fk_project_classifications_design_code",
        ),
        nullable=True,
    )
    research_design_source: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    research_design_method: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    research_design_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    research_design_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    research_design_alternatives: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )

    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    classifier_version: Mapped[str] = mapped_column(Text, nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(Text, nullable=False)

    context_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    context_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','completed','needs_review','failed')",
            name="ck_project_classifications_status",
        ),
        CheckConstraint(
            "domain_source IS NULL OR "
            "domain_source IN ('explicit','inferred','user_override')",
            name="ck_project_classifications_domain_source",
        ),
        CheckConstraint(
            "domain_method IS NULL OR "
            "domain_method IN ('explicit','heuristic','llm')",
            name="ck_project_classifications_domain_method",
        ),
        CheckConstraint(
            "domain_confidence IS NULL OR "
            "(domain_confidence >= 0.0 AND domain_confidence <= 1.0)",
            name="ck_project_classifications_domain_conf",
        ),
        CheckConstraint(
            "paper_type_source IS NULL OR "
            "paper_type_source IN "
            "('explicit','inferred','user_override')",
            name="ck_project_classifications_paper_source",
        ),
        CheckConstraint(
            "paper_type_method IS NULL OR "
            "paper_type_method IN ('explicit','heuristic','llm')",
            name="ck_project_classifications_paper_method",
        ),
        CheckConstraint(
            "paper_type_confidence IS NULL OR "
            "(paper_type_confidence >= 0.0 "
            "AND paper_type_confidence <= 1.0)",
            name="ck_project_classifications_paper_conf",
        ),
        CheckConstraint(
            "research_design_source IS NULL OR "
            "research_design_source IN "
            "('explicit','inferred','user_override')",
            name="ck_project_classifications_design_source",
        ),
        CheckConstraint(
            "research_design_method IS NULL OR "
            "research_design_method IN ('explicit','heuristic','llm')",
            name="ck_project_classifications_design_method",
        ),
        CheckConstraint(
            "research_design_confidence IS NULL OR "
            "(research_design_confidence >= 0.0 "
            "AND research_design_confidence <= 1.0)",
            name="ck_project_classifications_design_conf",
        ),
        Index("ix_project_classifications_status", "status"),
        Index(
            "ix_project_classifications_paper_type", "paper_type_code"
        ),
        Index(
            "ix_project_classifications_design", "research_design_code"
        ),
        Index(
            "ix_project_classifications_context_hash",
            "project_id",
            "context_hash",
        ),
    )


class ClassificationEvidence(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "classification_evidence"

    classification_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_classifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    target: Mapped[str] = mapped_column(Text, nullable=False)
    signal_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_location: Mapped[str] = mapped_column(Text, nullable=False)
    matched_text: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    target_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    evidence_meta: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "target IN ('domain','paper_type','research_design')",
            name="ck_classification_evidence_target",
        ),
        CheckConstraint(
            "weight >= 0.0 AND weight <= 1.0",
            name="ck_classification_evidence_weight",
        ),
        Index(
            "ix_classification_evidence_class_target",
            "classification_id",
            "target",
        ),
    )
