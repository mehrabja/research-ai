"""M39 F08 — manuscript drafts and immutable version content."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manuscript_versions",
        sa.Column("content_snapshot", postgresql.JSONB(), nullable=True),
    )
    op.create_table(
        "manuscript_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("manuscript_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manuscript_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("content", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("report_id", name="ux_manuscript_drafts_report"),
    )
    op.create_index("ix_manuscript_drafts_manuscript", "manuscript_drafts", ["manuscript_id"])
    op.create_index("ix_manuscript_drafts_updated", "manuscript_drafts", ["updated_at"])
    op.create_table(
        "manuscript_draft_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manuscript_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("saved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("saved_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("draft_id", "revision", name="ux_manuscript_draft_history_revision"),
    )
    op.create_index("ix_manuscript_draft_history_draft_saved", "manuscript_draft_history", ["draft_id", "saved_at"])


def downgrade() -> None:
    op.drop_index("ix_manuscript_draft_history_draft_saved", table_name="manuscript_draft_history")
    op.drop_table("manuscript_draft_history")
    op.drop_index("ix_manuscript_drafts_updated", table_name="manuscript_drafts")
    op.drop_index("ix_manuscript_drafts_manuscript", table_name="manuscript_drafts")
    op.drop_table("manuscript_drafts")
    op.drop_column("manuscript_versions", "content_snapshot")
