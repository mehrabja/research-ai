"""M39 project-owned provider routing policy."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
revision="0036"
down_revision="0035"
branch_labels=None
depends_on=None
def upgrade()->None:
    op.add_column("projects", sa.Column("provider_policy", sa.JSON(), nullable=True))
def downgrade()->None:
    op.drop_column("projects","provider_policy")
