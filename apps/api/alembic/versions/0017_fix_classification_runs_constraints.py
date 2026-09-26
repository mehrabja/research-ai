"""Fix classification_runs constraints.

Revision ID: 0017
Revises: 0016
"""
from __future__ import annotations

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Allow 'needs_review' as a run status (it's the current-state
    #    status when the classifier decides a review is needed).
    op.drop_constraint(
        "ck_classification_runs_status",
        "classification_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_classification_runs_status",
        "classification_runs",
        "status IN ('completed','needs_review','failed','skipped')",
    )

    # 2. Change FK to ON DELETE CASCADE so deleting a
    #    ProjectClassification does not try to UPDATE the run row
    #    (which is blocked by the append-only trigger).
    op.drop_constraint(
        "fk_classification_runs_classification_id",
        "classification_runs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_classification_runs_classification_id",
        "classification_runs",
        "project_classifications",
        ["classification_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_classification_runs_classification_id",
        "classification_runs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_classification_runs_classification_id",
        "classification_runs",
        "project_classifications",
        ["classification_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "ck_classification_runs_status",
        "classification_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_classification_runs_status",
        "classification_runs",
        "status IN ('completed','failed','skipped')",
    )