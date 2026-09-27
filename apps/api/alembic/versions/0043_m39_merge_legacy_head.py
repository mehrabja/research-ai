"""M39 — merge the legacy report soft-delete Alembic head."""
from __future__ import annotations

revision = "0043"
down_revision = ("0042", "14b3d4303f3f")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge-only revision. The legacy branch contains the report
    # soft-delete change and the 0042 chain contains the M39 changes.
    pass


def downgrade() -> None:
    # Merge-only revision.
    pass
