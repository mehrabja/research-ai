"""F08 — mutable manuscript autosave buffer.

Revision ID: 0036
Revises: 0035
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "manuscript_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("manuscript_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("content", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("manuscript_id", name="ux_manuscript_drafts_manuscript"),
    )
    op.create_index("ix_manuscript_drafts_report", "manuscript_drafts", ["report_id"])
    op.create_index("ix_manuscript_drafts_updated", "manuscript_drafts", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_manuscript_drafts_updated", table_name="manuscript_drafts")
    op.drop_index("ix_manuscript_drafts_report", table_name="manuscript_drafts")
    op.drop_table("manuscript_drafts")
