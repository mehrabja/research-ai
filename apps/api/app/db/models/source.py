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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin

SOURCE_STATUSES = (
    "metadata_only",
    "abstract_only",
    "full_text",
    "structured_full_text",
    "extraction_failed",
)

# Fixed embedding dimension. Changing it requires a migration +
# re-embedding + HNSW index rebuild.
EMBEDDING_DIM = 1536


def _in_check(
    column: str,
    values: tuple[str, ...],
    name: str,
) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class Source(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "sources"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    authors: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    doi: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_api: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    external_source_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    citation_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    abstract: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    full_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Non-monetary score, but precision still matters: Decimal.
    source_quality: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    # SQLAlchemy reserves `metadata`, so the Python attribute is `source_meta`.
    source_meta: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    # --- Extraction lifecycle (Milestone 8) -------------------------------
    # All nullable: historical Source rows remain valid until their next
    # extraction. ``extraction_pipeline_version`` participates in the
    # idempotency decision so a change to normalization, canonicalization,
    # chunking, or extractor behavior triggers a rebuild even when the raw
    # content hash is unchanged.
    content_hash: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    extraction_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    content_type: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    content_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    extraction_pipeline_version: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        _in_check(
            "status",
            SOURCE_STATUSES,
            "ck_sources_status",
        ),
        CheckConstraint(
            "year IS NULL OR (year >= 1000 AND year <= 2200)",
            name="ck_sources_year",
        ),
        CheckConstraint(
            "citation_count IS NULL OR citation_count >= 0",
            name="ck_sources_citation_count",
        ),
        CheckConstraint(
            "source_quality IS NULL OR "
            "(source_quality >= 0 AND source_quality <= 1)",
            name="ck_sources_quality_range",
        ),
        Index(
            "ix_sources_report_id",
            "report_id",
        ),
        Index(
            "ix_sources_doi",
            "doi",
        ),
        Index(
            "ix_sources_source_api_external_id",
            "source_api",
            "external_source_id",
        ),
        Index(
            "ix_sources_status",
            "status",
        ),
    )


class Chunk(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "chunks"

    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    from pgvector.sqlalchemy import Vector

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM),
        nullable=True,
    )

    embedding_model_version: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    chunk_meta: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    # --- Chunk provenance (Milestone 8) -----------------------------------
    # Half-open character range into the canonical source text. Nullable
    # so historical chunks (pre-M8) remain valid.
    char_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    char_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "chunk_index",
            name="ux_chunks_source_index",
        ),
        CheckConstraint(
            "chunk_index >= 0",
            name="ck_chunks_index_nonneg",
        ),
        CheckConstraint(
            "token_count IS NULL OR token_count >= 0",
            name="ck_chunks_token_count_nonneg",
        ),
        CheckConstraint(
            "char_start IS NULL OR char_start >= 0",
            name="ck_chunks_char_start_nonneg",
        ),
        CheckConstraint(
            "char_end IS NULL OR char_end > 0",
            name="ck_chunks_char_end_pos",
        ),
        CheckConstraint(
            "char_start IS NULL OR char_end IS NULL "
            "OR char_end > char_start",
            name="ck_chunks_char_range",
        ),
        CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_chunks_page_number_pos",
        ),
        Index(
            "ix_chunks_source_id_chunk_index",
            "source_id",
            "chunk_index",
        ),
    )


class CitationLink(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "citation_links"

    generation_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("generation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    claim_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )

    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
    )

    support_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    similarity_score: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    entailment_check: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    numeric_entity_check: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    validation_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )

    __table_args__ = (
        _in_check(
            "support_type",
            ("direct", "synthesis"),
            "ck_citation_links_support_type",
        ),
        CheckConstraint(
            "entailment_check IS NULL OR entailment_check IN "
            "('supported','contradicted','unclear')",
            name="ck_citation_links_entailment",
        ),
        _in_check(
            "validation_status",
            ("pending", "passed", "failed", "needs_review"),
            "ck_citation_links_validation_status",
        ),
        Index(
            "ix_citation_links_generation_run",
            "generation_run_id",
        ),
        Index(
            "ix_citation_links_source",
            "source_id",
        ),
        Index(
            "ix_citation_links_validation_status",
            "validation_status",
        ),
    )
