"""add source discovery identity and source_added event

Revision ID: 0007
Revises: 14b3d4303f3f
Create Date: 2026-09-17

Two independent changes are bundled here because they both belong to
the M7 Source Discovery corrective milestone and are applied together:

1. Partial unique index ``ux_sources_report_api_external`` on
   ``sources (report_id, source_api, external_source_id)`` where both
   identity columns are non-NULL. This enforces idempotent registration
   of provider-sourced rows at the database level.

2. Extend the ``ck_report_events_type`` and ``ck_report_events_shape``
   CHECK constraints to allow ``event_type = 'source_added'`` with the
   same non-status shape used by ``source_extracted``.

Downgrade requires that no ``source_added`` events exist in the
database. If any are present, the downgrade will fail (by design).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006_detection_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ux_sources_report_api_external",
        "sources",
        ["report_id", "source_api", "external_source_id"],
        unique=True,
        postgresql_where=sa.text(
            "source_api IS NOT NULL "
            "AND external_source_id IS NOT NULL"
        ),
    )

    op.drop_constraint(
        "ck_report_events_type", "report_events", type_="check"
    )
    op.create_check_constraint(
        "ck_report_events_type",
        "report_events",
        "event_type IN "
        "('status_transition','version_created',"
        "'source_extracted','source_added')",
    )

    op.drop_constraint(
        "ck_report_events_shape", "report_events", type_="check"
    )
    op.create_check_constraint(
        "ck_report_events_shape",
        "report_events",
        "(event_type = 'status_transition'"
        " AND from_status IS NOT NULL"
        " AND to_status IS NOT NULL"
        " AND from_status <> to_status"
        " AND version_id IS NULL)"
        " OR "
        "(event_type = 'version_created'"
        " AND version_id IS NOT NULL"
        " AND from_status IS NULL"
        " AND to_status IS NULL)"
        " OR "
        "(event_type IN ('source_extracted','source_added')"
        " AND from_status IS NULL"
        " AND to_status IS NULL"
        " AND version_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_report_events_shape", "report_events", type_="check"
    )
    op.create_check_constraint(
        "ck_report_events_shape",
        "report_events",
        "(event_type = 'status_transition'"
        " AND from_status IS NOT NULL"
        " AND to_status IS NOT NULL"
        " AND from_status <> to_status"
        " AND version_id IS NULL)"
        " OR "
        "(event_type = 'version_created'"
        " AND version_id IS NOT NULL"
        " AND from_status IS NULL"
        " AND to_status IS NULL)"
        " OR "
        "(event_type = 'source_extracted'"
        " AND from_status IS NULL"
        " AND to_status IS NULL"
        " AND version_id IS NULL)",
    )

    op.drop_constraint(
        "ck_report_events_type", "report_events", type_="check"
    )
    op.create_check_constraint(
        "ck_report_events_type",
        "report_events",
        "event_type IN "
        "('status_transition','version_created',"
        "'source_extracted')",
    )

    op.drop_index(
        "ux_sources_report_api_external", table_name="sources"
    )