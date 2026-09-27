"""F11 — permit Stripe in provider-constrained billing tables.

Revision ID: 0041
Revises: 0040
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_subscriptions_provider",
        "subscriptions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_subscriptions_provider",
        "subscriptions",
        "provider IN ('none','fake','stripe')",
    )
    op.drop_constraint(
        "ck_billing_events_provider",
        "billing_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_billing_events_provider",
        "billing_events",
        "provider IN ('none','fake','stripe')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_billing_events_provider",
        "billing_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_billing_events_provider",
        "billing_events",
        "provider IN ('none','fake')",
    )
    op.drop_constraint(
        "ck_subscriptions_provider",
        "subscriptions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_subscriptions_provider",
        "subscriptions",
        "provider IN ('none','fake')",
    )
