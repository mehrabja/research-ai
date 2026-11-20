"""M39 F01 — allow Stripe as a subscription provider."""
from __future__ import annotations

from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_subscriptions_provider", "subscriptions", type_="check"
    )
    op.create_check_constraint(
        "ck_subscriptions_provider",
        "subscriptions",
        "provider IN ('none','fake','stripe')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_subscriptions_provider", "subscriptions", type_="check"
    )
    op.create_check_constraint(
        "ck_subscriptions_provider",
        "subscriptions",
        "provider IN ('none','fake')",
    )
