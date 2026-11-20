"""M39 F12 — allow Stripe as a billing provider.

The domain/model provider set includes stripe but the original M37
constraints only allowed none and fake. Keep the database contract
aligned with the application domain before real Stripe operations are used.
"""
from alembic import op


revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def _replace_provider_constraint(table: str, constraint: str) -> None:
    op.execute(
        f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}"
    )
    op.create_check_constraint(
        constraint,
        table,
        "provider IN ('none', 'fake', 'stripe')",
    )


def upgrade() -> None:
    _replace_provider_constraint("subscriptions", "ck_subscriptions_provider")
    _replace_provider_constraint("billing_events", "ck_billing_events_provider")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE subscriptions "
        "DROP CONSTRAINT IF EXISTS ck_subscriptions_provider"
    )
    op.create_check_constraint(
        "ck_subscriptions_provider",
        "subscriptions",
        "provider IN ('none', 'fake')",
    )
    op.execute(
        "ALTER TABLE billing_events "
        "DROP CONSTRAINT IF EXISTS ck_billing_events_provider"
    )
    op.create_check_constraint(
        "ck_billing_events_provider",
        "billing_events",
        "provider IN ('none', 'fake')",
    )
