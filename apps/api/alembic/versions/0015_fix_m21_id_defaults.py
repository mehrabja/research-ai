"""Fix missing gen_random_uuid() default on M21 id columns.

Revision ID: 0015
Revises: 0014
"""
from __future__ import annotations

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_TABLES = (
    "research_designs",
    "research_domains",
    "paper_types",
    "project_classifications",
    "classification_evidence",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN id SET DEFAULT gen_random_uuid()"
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN id DROP DEFAULT"
        )