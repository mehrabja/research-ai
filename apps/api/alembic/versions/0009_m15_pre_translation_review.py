"""M15 — add pre_translation_review status and diff_from_previous column.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


_NEW_STATUSES = (
    "draft", "searching", "extracting", "retrieving", "generating",
    "review_1", "detecting", "humanizing", "pre_translation_review",
    "translating", "post_translation_review", "converging", "review_2",
    "validating", "completed", "failed", "cancelled",
)

_OLD_STATUSES = (
    "draft", "searching", "extracting", "retrieving", "generating",
    "review_1", "detecting", "humanizing",
    "translating", "post_translation_review", "converging", "review_2",
    "validating", "completed", "failed", "cancelled",
)


def _status_check_sql(statuses: tuple[str, ...]) -> str:
    quoted = ",".join(f"'{s}'" for s in statuses)
    return f"status IN ({quoted})"


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        cols = {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False
    return column in cols


def _drop_status_check() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            cname text;
        BEGIN
            FOR cname IN
                SELECT con.conname
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                WHERE rel.relname = 'reports'
                  AND con.contype = 'c'
                  AND pg_get_constraintdef(con.oid) LIKE '%status%'
            LOOP
                EXECUTE format('ALTER TABLE reports DROP CONSTRAINT %I', cname);
            END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    # 1. Add diff_from_previous if missing
    if not _column_exists("report_versions", "diff_from_previous"):
        op.add_column(
            "report_versions",
            sa.Column("diff_from_previous", sa.Text(), nullable=True),
        )

    # 2. Replace status CHECK to include pre_translation_review
    _drop_status_check()
    op.create_check_constraint(
        "ck_reports_status",
        "reports",
        _status_check_sql(_NEW_STATUSES),
    )


def downgrade() -> None:
    _drop_status_check()
    op.create_check_constraint(
        "ck_reports_status",
        "reports",
        _status_check_sql(_OLD_STATUSES),
    )
    if _column_exists("report_versions", "diff_from_previous"):
        op.drop_column("report_versions", "diff_from_previous")