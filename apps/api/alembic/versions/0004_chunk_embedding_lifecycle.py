"""add chunk embedding lifecycle and lexical index

Revision ID: 0004_chunk_embedding_lifecycle
Revises: 0003_extraction_chunk_prov
Create Date: 2026-09-17

Adds:
  * usage_logs.metadata JSONB (nullable) for provider request IDs.
  * chunk embedding lifecycle: 7 columns + 2 CHECK constraints.
  * GIN lexical index ix_chunks_content_tsv.
  * HNSW vector index ix_chunks_embedding_hnsw (idempotent).

Revision id is deliberately kept short: the alembic
``alembic_version.version_num`` column is VARCHAR(32).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_chunk_embedding_lifecycle"
down_revision: Union[str, None] = "0003_extraction_chunk_prov"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. usage_logs.metadata (D4 — confirmed absent).
    op.add_column(
        "usage_logs",
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )

    # 2. Chunk embedding lifecycle.
    op.add_column(
        "chunks",
        sa.Column("embedding_input_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "chunks",
        sa.Column("embedding_provider", sa.Text(), nullable=True),
    )
    op.add_column(
        "chunks",
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "embedding_status",
            sa.Text(),
            nullable=True,
            server_default=sa.text("'pending'"),
        ),
    )
    op.add_column(
        "chunks",
        sa.Column("embedding_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "embedding_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "embedding_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_chunks_embedding_dimensions_pos",
        "chunks",
        "embedding_dimensions IS NULL OR embedding_dimensions > 0",
    )
    op.create_check_constraint(
        "ck_chunks_embedding_status",
        "chunks",
        "embedding_status IS NULL OR embedding_status IN "
        "('pending','processing','completed','failed')",
    )

    # 3. GIN lexical index.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_content_tsv "
        "ON chunks USING gin (to_tsvector('simple', content))"
    )

    # 4. HNSW vector index (idempotent).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
        "ON chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_chunks_content_tsv")
    op.drop_constraint(
        "ck_chunks_embedding_status", "chunks", type_="check"
    )
    op.drop_constraint(
        "ck_chunks_embedding_dimensions_pos", "chunks", type_="check"
    )
    op.drop_column("chunks", "embedding_completed_at")
    op.drop_column("chunks", "embedding_started_at")
    op.drop_column("chunks", "embedding_error")
    op.drop_column("chunks", "embedding_status")
    op.drop_column("chunks", "embedding_dimensions")
    op.drop_column("chunks", "embedding_provider")
    op.drop_column("chunks", "embedding_input_hash")
    op.drop_column("usage_logs", "metadata")