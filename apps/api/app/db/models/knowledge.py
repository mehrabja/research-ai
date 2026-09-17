
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin
from app.db.models.source import EMBEDDING_DIM


class VoiceProfile(Base, UUIDPKMixin):
    __tablename__ = "voice_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(Text, nullable=False)
    formality: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    avg_sentence_length: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    sentence_length_variance: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    active_ratio: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    first_person: Mapped[str | None] = mapped_column(Text, nullable=True)
    nominalization_tolerance: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("user_id", "language", name="ux_voice_profiles_user_lang"),
    )


class StyleExemplar(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "style_exemplars"

    domain: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    from pgvector.sqlalchemy import Vector  # noqa: WPS433

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )
    human_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "license IS NULL OR length(license) > 0",
            name="ck_style_exemplars_license_present",
        ),
        Index("ix_style_exemplars_domain_language", "domain", "language"),
    )


class AITellPattern(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "ai_tell_patterns"

    language: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    replacement_pool: Mapped[dict] = mapped_column(JSONB, nullable=False)
    severity: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("1")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    version: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'1.0.0'")
    )

    __table_args__ = (
        CheckConstraint(
            "severity >= 0 AND severity <= 10", name="ck_ai_tell_patterns_severity"
        ),
        Index("ix_ai_tell_patterns_language_active", "language", "active"),
        Index("ix_ai_tell_patterns_domain_active", "domain", "active"),
    )


class DetectionThreshold(Base, UUIDPKMixin):
    __tablename__ = "detection_thresholds"

    detector: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    calibration_set_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    percentiles: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    calibrated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "detector", "domain", "language",
            name="ux_detection_thresholds_detector_domain_lang",
        ),
        CheckConstraint(
            "threshold >= 0 AND threshold <= 1", name="ck_detection_thresholds_range"
        ),
    )


class TerminologyGlossary(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "terminology_glossary"

    source_term: Mapped[str] = mapped_column(Text, nullable=False)
    target_term: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_pair: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        Index("ix_terminology_glossary_domain_lang_pair", "domain", "language_pair"),
        Index("ix_terminology_glossary_locked", "locked"),
    )
