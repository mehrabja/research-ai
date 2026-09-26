"""M39 billing provider expansion and normalized billing records."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision="0035"
down_revision="0034"
branch_labels=None
depends_on=None

def upgrade()->None:
    for table,constraint in (
        ("subscriptions","ck_subscriptions_provider"),
        ("billing_events","ck_billing_events_provider"),
    ):
        op.drop_constraint(constraint,table_name=table,type_="check")
    op.create_check_constraint(
        "ck_subscriptions_provider","subscriptions",
        "provider IN ('none','fake','stripe')",
    )
    op.create_check_constraint(
        "ck_billing_events_provider","billing_events",
        "provider IN ('none','fake','stripe')",
    )

    op.create_table(
        "billing_customers",
        sa.Column("id",sa.UUID(),server_default=sa.text("gen_random_uuid()"),primary_key=True),
        sa.Column("workspace_id",sa.UUID(),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False,unique=True),
        sa.Column("provider",sa.Text(),nullable=False),
        sa.Column("provider_customer_id",sa.Text(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.UniqueConstraint("provider","provider_customer_id",name="ux_billing_customers_provider_customer"),
    )
    op.create_index("ix_billing_customers_workspace","billing_customers",["workspace_id"])

    op.create_table(
        "billing_checkout_sessions",
        sa.Column("id",sa.UUID(),server_default=sa.text("gen_random_uuid()"),primary_key=True),
        sa.Column("workspace_id",sa.UUID(),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),
        sa.Column("plan_id",sa.UUID(),sa.ForeignKey("plans.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("provider",sa.Text(),nullable=False),
        sa.Column("provider_session_id",sa.Text(),nullable=False),
        sa.Column("status",sa.Text(),server_default=sa.text("'created'"),nullable=False),
        sa.Column("checkout_url",sa.Text()),
        sa.Column("idempotency_key",sa.Text(),nullable=False,unique=True),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.UniqueConstraint("provider","provider_session_id",name="ux_billing_checkout_provider_session"),
    )
    op.create_index("ix_billing_checkout_workspace_created","billing_checkout_sessions",["workspace_id","created_at"])

    op.create_table(
        "billing_invoices",
        sa.Column("id",sa.UUID(),server_default=sa.text("gen_random_uuid()"),primary_key=True),
        sa.Column("workspace_id",sa.UUID(),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),
        sa.Column("provider",sa.Text(),nullable=False),
        sa.Column("provider_invoice_id",sa.Text(),nullable=False),
        sa.Column("status",sa.Text(),nullable=False),
        sa.Column("currency",sa.Text(),nullable=False),
        sa.Column("amount_due",sa.Numeric(18,8),server_default=sa.text("0"),nullable=False),
        sa.Column("amount_paid",sa.Numeric(18,8),server_default=sa.text("0"),nullable=False),
        sa.Column("hosted_invoice_url",sa.Text()),
        sa.Column("invoice_pdf_url",sa.Text()),
        sa.Column("period_start",sa.DateTime(timezone=True)),
        sa.Column("period_end",sa.DateTime(timezone=True)),
        sa.Column("metadata",sa.JSON()),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.UniqueConstraint("provider","provider_invoice_id",name="ux_billing_invoices_provider_invoice"),
    )
    op.create_index("ix_billing_invoices_workspace_created","billing_invoices",["workspace_id","created_at"])

def downgrade()->None:
    op.drop_index("ix_billing_invoices_workspace_created",table_name="billing_invoices")
    op.drop_table("billing_invoices")
    op.drop_index("ix_billing_checkout_workspace_created",table_name="billing_checkout_sessions")
    op.drop_table("billing_checkout_sessions")
    op.drop_index("ix_billing_customers_workspace",table_name="billing_customers")
    op.drop_table("billing_customers")
    op.drop_constraint("ck_subscriptions_provider",table_name="subscriptions",type_="check")
    op.drop_constraint("ck_billing_events_provider",table_name="billing_events",type_="check")
    op.create_check_constraint("ck_subscriptions_provider","subscriptions","provider IN ('none','fake')")
    op.create_check_constraint("ck_billing_events_provider","billing_events","provider IN ('none','fake')")
