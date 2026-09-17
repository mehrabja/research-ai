"""add extraction lifecycle and chunk provenance

Revision ID: 0003_extraction_chunk_prov
Revises: 0002_add_report_events
Create Date: 2026-09-17

Adds:
  * sources: 6 extraction-lifecycle columns (all nullable).
  * chunks: 3 provenance columns (char_start, char_end, page_number)
    plus 4 CHECK constraints.
  * report_events: extends ``ck_report_events_type`` and
    ``ck_report_events_shape`` to recognise the new
    ``source_extracted`` event type.

No existing column is renamed, dropped, or made non-nullable. All
new columns are nullable so historical rows remain valid.

Revision id is deliberately kept short: the alembic
``alembic_version.version_num`` column is VARCHAR(32).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003_extraction_chunk_prov"
down_revision: Union[str, None] = "0002_add_report_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. sources — extraction lifecycle
    # ------------------------------------------------------------------
    op.add_column(
        "sources",
        sa.Column("content_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "sources",
        sa.Column("extraction_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column("content_type", sa.Text(), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column("content_length", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sources",
        sa.Column(
            "extraction_pipeline_version", sa.Text(), nullable=True
        ),
    )

    # ------------------------------------------------------------------
    # 2. chunks — provenance
    # ------------------------------------------------------------------
    op.add_column(
        "chunks",
        sa.Column("char_start", sa.Integer(), nullable=True),
    )
    op.add_column(
        "chunks",
        sa.Column("char_end", sa.Integer(), nullable=True),
    )
    op.add_column(
        "chunks",
        sa.Column("page_number", sa.Integer(), nullable=True),
    )

    op.create_check_constraint(
        "ck_chunks_char_start_nonneg",
        "chunks",
        "char_start IS NULL OR char_start >= 0",
    )
    op.create_check_constraint(
        "ck_chunks_char_end_pos",
        "chunks",
        "char_end IS NULL OR char_end > 0",
    )
    op.create_check_constraint(
        "ck_chunks_char_range",
        "chunks",
        "char_start IS NULL OR char_end IS NULL "
        "OR char_end > char_start",
    )
    op.create_check_constraint(
        "ck_chunks_page_number_pos",
        "chunks",
        "page_number IS NULL OR page_number >= 1",
    )

    # ------------------------------------------------------------------
    # 3. report_events — accept source_extracted
    # ------------------------------------------------------------------
    op.drop_constraint(
        "ck_report_events_type",
        "report_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_report_events_type",
        "report_events",
        "event_type IN "
        "('status_transition','version_created','source_extracted')",
    )

    op.drop_constraint(
        "ck_report_events_shape",
        "report_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_report_events_shape",
        "report_events",
        "(event_type = 'status_transition'"
        " AND from_status IS NOT NULL"
        " AND to_status IS NOT NULL"
        " AND from_status <> to_status"
        " AND version_id IS NULL)"
        " OR "
        "(event_type = 'version_created'"
        " AND version_id IS NOT NULL"
        " AND from_status IS NULL"
        " AND to_status IS NULL)"
        " OR "
        "(event_type = 'source_extracted'"
        " AND from_status IS NULL"
        " AND to_status IS NULL"
        " AND version_id IS NULL)",
    )


def downgrade() -> None:
    # Reverse report_events CHECKs to their pre-M8 shape.
    op.drop_constraint(
        "ck_report_events_shape",
        "report_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_report_events_shape",
        "report_events",
        "(event_type = 'status_transition'"
        " AND from_status IS NOT NULL"
        " AND to_status IS NOT NULL"
        " AND from_status <> to_status"
        " AND version_id IS NULL)"
        " OR "
        "(event_type = 'version_created'"
        " AND version_id IS NOT NULL"
        " AND from_status IS NULL"
        " AND to_status IS NULL)",
    )

    op.drop_constraint(
        "ck_report_events_type",
        "report_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_report_events_type",
        "report_events",
        "event_type IN ('status_transition','version_created')",
    )

    # Reverse chunks provenance.
    op.drop_constraint(
        "ck_chunks_page_number_pos", "chunks", type_="check"
    )
    op.drop_constraint(
        "ck_chunks_char_range", "chunks", type_="check"
    )
    op.drop_constraint(
        "ck_chunks_char_end_pos", "chunks", type_="check"
    )
    op.drop_constraint(
        "ck_chunks_char_start_nonneg", "chunks", type_="check"
    )
    op.drop_column("chunks", "page_number")
    op.drop_column("chunks", "char_end")
    op.drop_column("chunks", "char_start")

    # Reverse sources extraction columns.
    op.drop_column("sources", "extraction_pipeline_version")
    op.drop_column("sources", "content_length")
    op.drop_column("sources", "content_type")
    op.drop_column("sources", "extraction_error")
    op.drop_column("sources", "extracted_at")
    op.drop_column("sources", "content_hash")