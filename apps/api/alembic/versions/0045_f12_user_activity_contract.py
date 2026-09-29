"""F12 user activity contract.

No database objects are introduced. The activity feed is a safe projection
of existing durable security records (sessions, API tokens, OAuth accounts,
and user lifecycle timestamps), keeping raw audit logs server-side.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Contract-only revision: no DDL required.
    pass


def downgrade() -> None:
    pass
