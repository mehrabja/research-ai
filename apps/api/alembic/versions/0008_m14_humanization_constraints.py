"""M14 — reconcile humanization schema drift (constraints + indexes)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


_RUN_CHECKS = (
    ("ck_humanization_runs_detection_before",
     "detection_score_before IS NULL OR (detection_score_before >= 0 AND detection_score_before <= 1)"),
    ("ck_humanization_runs_detection_after",
     "detection_score_after IS NULL OR (detection_score_after >= 0 AND detection_score_after <= 1)"),
    ("ck_humanization_runs_cost", "cost_usd IS NULL OR cost_usd >= 0"),
)
_ITER_CHECKS = (
    ("ck_humanization_iterations_score_range",
     "detection_score_mean IS NULL OR (detection_score_mean >= 0 AND detection_score_mean <= 1)"),
    ("ck_humanization_iterations_cost", "cost_usd IS NULL OR cost_usd >= 0"),
)
_REWRITE_CHECKS = (
    ("ck_humanization_rewrites_cost", "cost_usd IS NULL OR cost_usd >= 0"),
)
_RUN_INDEXES = (("ix_humanization_runs_report_created", ("report_id", "created_at")),)
_REWRITE_INDEXES = (("ix_humanization_rewrites_segment", ("humanization_run_id", "segment_id")),)


def _has_table(insp, t):
    try: return t in insp.get_table_names()
    except Exception: return False


def _has_check(insp, t, n):
    try: return n in {c.get("name") for c in insp.get_check_constraints(t)}
    except Exception: return False


def _has_index(insp, t, n):
    try: return n in {i.get("name") for i in insp.get_indexes(t)}
    except Exception: return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table, checks in (
        ("humanization_runs", _RUN_CHECKS),
        ("humanization_iterations", _ITER_CHECKS),
        ("humanization_rewrites", _REWRITE_CHECKS),
    ):
        if not _has_table(insp, table):
            continue
        for name, cond in checks:
            if not _has_check(insp, table, name):
                op.create_check_constraint(name, table, cond)

    for table, indexes in (
        ("humanization_runs", _RUN_INDEXES),
        ("humanization_rewrites", _REWRITE_INDEXES),
    ):
        if not _has_table(insp, table):
            continue
        for name, cols in indexes:
            if not _has_index(insp, table, name):
                op.create_index(name, table, list(cols))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table, indexes in (
        ("humanization_rewrites", _REWRITE_INDEXES),
        ("humanization_runs", _RUN_INDEXES),
    ):
        if not _has_table(insp, table):
            continue
        for name, _ in indexes:
            if _has_index(insp, table, name):
                op.drop_index(name, table_name=table)

    for table, checks in (
        ("humanization_rewrites", _REWRITE_CHECKS),
        ("humanization_iterations", _ITER_CHECKS),
        ("humanization_runs", _RUN_CHECKS),
    ):
        if not _has_table(insp, table):
            continue
        for name, _ in checks:
            if _has_check(insp, table, name):
                op.drop_constraint(name, table, type_="check")