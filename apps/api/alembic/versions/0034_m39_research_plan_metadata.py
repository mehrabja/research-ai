"""M39 research plan editable metadata."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("research_plans", sa.Column("plan_meta", sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column("research_plans", "plan_meta")
