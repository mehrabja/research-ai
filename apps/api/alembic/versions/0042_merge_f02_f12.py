"""Merge legacy report soft-delete branch into F02-F12 migration chain.

Revision ID: 0042
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "0042"
down_revision: tuple[str, str] = ("0041", "14b3d4303f3f")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
