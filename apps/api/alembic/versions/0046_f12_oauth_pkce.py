"""F12 — persist OAuth PKCE challenges.

Revision ID: 0046
Revises: 0045
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "oauth_states",
        sa.Column("code_challenge", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("oauth_states", "code_challenge")
