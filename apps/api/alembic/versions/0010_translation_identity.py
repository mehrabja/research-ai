"""M16/M17 — translation identity: source_version_id + profile_id."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0010"
down_revision = "0009"   # VERIFY با alembic heads
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        return column in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def _has_index(table: str, name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        return name in {i["name"] for i in insp.get_indexes(table)}
    except Exception:
        return False


def upgrade() -> None:
    if not _has_column("translation_runs", "source_version_id"):
        op.add_column(
            "translation_runs",
            sa.Column(
                "source_version_id",
                PGUUID(as_uuid=True),
                sa.ForeignKey("report_versions.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if not _has_column("translation_runs", "profile_id"):
        op.add_column(
            "translation_runs",
            sa.Column("profile_id", sa.Text(), nullable=True),
        )
    if not _has_index("translation_runs", "ux_translation_runs_identity"):
        op.create_index(
            "ux_translation_runs_identity",
            "translation_runs",
            [
                "report_id", "source_version_id",
                "source_lang", "target_lang", "profile_id",
            ],
            unique=True,
            postgresql_where=sa.text("status = 'success'"),
        )


def downgrade() -> None:
    if _has_index("translation_runs", "ux_translation_runs_identity"):
        op.drop_index(
            "ux_translation_runs_identity", table_name="translation_runs"
        )
    if _has_column("translation_runs", "profile_id"):
        op.drop_column("translation_runs", "profile_id")
    if _has_column("translation_runs", "source_version_id"):
        op.drop_column("translation_runs", "source_version_id")