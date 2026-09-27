"""F12 — TOTP MFA state.

Revision ID: 0039
Revises: 0038
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("mfa_secret", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("mfa_recovery_code_hashes", postgresql.JSONB(), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "mfa_recovery_code_hashes")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "mfa_enabled")
