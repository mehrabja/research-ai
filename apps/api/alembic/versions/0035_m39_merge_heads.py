"""M39 — reconcile the legacy report soft-delete branch with M37/M39.
Revision ID: 0035
Revises: 0034, 14b3d4303f3f
"""
from __future__ import annotations

revision = "0035"
down_revision = ("0034", "14b3d4303f3f")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge-only migration. Both parent branches already contain their
    # complete schema changes; no additional DDL is required here.
    pass


def downgrade() -> None:
    # Merge-only revision; reverting moves Alembic back to both parents.
    pass
