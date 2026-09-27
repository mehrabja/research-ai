"""M39 F11 — billing invoice index."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_invoice_id", sa.Text(), nullable=False),
        sa.Column("provider_customer_id", sa.Text(), nullable=True),
        sa.Column("provider_subscription_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("amount_due", sa.Numeric(18, 2), nullable=True),
        sa.Column("amount_paid", sa.Numeric(18, 2), nullable=True),
        sa.Column("hosted_invoice_url", sa.Text(), nullable=True),
        sa.Column("invoice_pdf_url", sa.Text(), nullable=True),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("provider", "provider_invoice_id", name="ux_billing_invoices_provider_id"),
    )
    op.create_index(
        "ix_billing_invoices_workspace_created",
        "billing_invoices",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_billing_invoices_workspace_created", table_name="billing_invoices")
    op.drop_table("billing_invoices")
