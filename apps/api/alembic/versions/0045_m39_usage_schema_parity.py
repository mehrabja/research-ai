"""M39 F13 — repair usage_events schema parity for drifted databases.

M39 F01 (0038) owns usage_class. This defensive migration is a no-op on
databases that already match 0038, while repairing databases where Alembic
records the migration as applied but the physical column/constraint is absent.
"""
from alembic import op


revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE usage_events "
        "ADD COLUMN IF NOT EXISTS usage_class TEXT "
        "DEFAULT 'internal' NOT NULL"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_usage_events_class'
                  AND conrelid = 'usage_events'::regclass
            ) THEN
                ALTER TABLE usage_events
                ADD CONSTRAINT ck_usage_events_class
                CHECK (usage_class IN ('provider', 'internal', 'billable'));
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE usage_events "
        "DROP CONSTRAINT IF EXISTS ck_usage_events_class"
    )
    op.execute(
        "ALTER TABLE usage_events "
        "DROP COLUMN IF EXISTS usage_class"
    )
