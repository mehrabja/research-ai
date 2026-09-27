"""F12 — OAuth account linkage.

Revision ID: 0040
Revises: 0039
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "oauth_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_user_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider","provider_user_id",name="ux_oauth_accounts_provider_user"),
        sa.UniqueConstraint("user_id","provider",name="ux_oauth_accounts_user_provider"),
    )
    op.create_index("ix_oauth_accounts_user","oauth_accounts",["user_id"])

def downgrade() -> None:
    op.drop_index("ix_oauth_accounts_user", table_name="oauth_accounts")
    op.drop_table("oauth_accounts")
