"""M24 — Research Planning Engine schema.

Revision ID: 0019
Revises: 0018
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_M24_EVENTS = (
    "research_plan_generation_started",
    "research_plan_generation_completed",
    "research_plan_generation_failed",
    "research_plan_generation_skipped",
)

_EVENT_CHECK = (
    "event_type IN ("
    "'project_created','project_updated','project_archived',"
    "'classification_started','classification_completed',"
    "'classification_recomputed','classification_overridden',"
    "'classification_failed','classification_skipped',"
    "'literature_analysis_started','literature_analysis_completed',"
    "'literature_analysis_failed','literature_analysis_skipped',"
    "'literature_screening_overridden',"
    "'literature_cluster_completed','literature_gap_detected',"
    "'research_plan_generation_started',"
    "'research_plan_generation_completed',"
    "'research_plan_generation_failed',"
    "'research_plan_generation_skipped'"
    ")"
)


def upgrade() -> None:
    op.create_table(
        "research_plans",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False,
                  server_default=sa.text("'draft'")),
        sa.Column("planner_version", sa.Text(), nullable=False),
        sa.Column("planning_mode", sa.Text(), nullable=False,
                  server_default=sa.text("'deterministic'")),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("literature_run_id", PGUUID(as_uuid=True),
                  nullable=True),
        sa.Column("domain_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("paper_type_code", sa.Text(), nullable=True),
        sa.Column("research_design_code", sa.Text(), nullable=True),
        sa.Column("research_objective_snapshot", sa.Text(), nullable=True),
        sa.Column("research_questions_snapshot", JSONB, nullable=True),
        sa.Column("hypotheses_snapshot", JSONB, nullable=True),
        sa.Column("budget", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("completeness_score", sa.Numeric(), nullable=True),
        sa.Column("coverage_score", sa.Numeric(), nullable=True),
        sa.Column("validation_status", sa.Text(), nullable=False,
                  server_default=sa.text("'pending'")),
        sa.Column("validation_errors", JSONB, nullable=True),
        sa.Column("coverage_summary", JSONB, nullable=True),
        sa.Column("supersedes_plan_id", PGUUID(as_uuid=True),
                  nullable=True),
        sa.Column("created_by", PGUUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_research_plans_project"),
        sa.ForeignKeyConstraint(
            ["literature_run_id"], ["literature_intelligence_runs.id"],
            ondelete="SET NULL",
            name="fk_research_plans_literature_run"),
        sa.ForeignKeyConstraint(
            ["domain_id"], ["research_domains.id"], ondelete="SET NULL",
            name="fk_research_plans_domain"),
        sa.ForeignKeyConstraint(
            ["paper_type_code"], ["paper_types.code"],
            ondelete="SET NULL", name="fk_research_plans_paper_type"),
        sa.ForeignKeyConstraint(
            ["research_design_code"], ["research_designs.code"],
            ondelete="SET NULL", name="fk_research_plans_design"),
        sa.ForeignKeyConstraint(
            ["supersedes_plan_id"], ["research_plans.id"],
            ondelete="SET NULL", name="fk_research_plans_supersedes"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL",
            name="fk_research_plans_created_by"),
        sa.CheckConstraint(
            "status IN ('draft','ready','superseded','failed','archived')",
            name="ck_research_plans_status"),
        sa.CheckConstraint(
            "planning_mode IN "
            "('deterministic','hybrid','deterministic_fallback')",
            name="ck_research_plans_mode"),
        sa.CheckConstraint(
            "validation_status IN ('pending','valid','invalid')",
            name="ck_research_plans_validation_status"),
        sa.CheckConstraint("version >= 1",
                           name="ck_research_plans_version"),
        sa.UniqueConstraint(
            "project_id", "version",
            name="ux_research_plans_project_version"),
    )
    op.create_index("ix_research_plans_project",
                    "research_plans", ["project_id"])
    op.create_index("ix_research_plans_project_status",
                    "research_plans", ["project_id", "status"])
    op.create_index("ix_research_plans_project_version",
                    "research_plans", ["project_id", "version"])
    op.create_index(
        "ux_research_plans_context_completed",
        "research_plans",
        ["project_id", "context_hash", "planner_version"],
        unique=True,
        postgresql_where=sa.text("status = 'ready'"),
    )

    op.create_table(
        "research_plan_sections",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("section_type", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("word_budget", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("budget_weight", sa.Numeric(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("evidence_coverage_target", sa.Numeric(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False,
                  server_default=sa.text("'active'")),
        sa.Column("section_meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["research_plans.id"], ondelete="CASCADE",
            name="fk_research_plan_sections_plan"),
        sa.UniqueConstraint("plan_id", "section_key",
                            name="ux_research_plan_sections_key"),
        sa.UniqueConstraint("plan_id", "display_order",
                            name="ux_research_plan_sections_order"),
        sa.CheckConstraint("display_order >= 0",
                           name="ck_research_plan_sections_order"),
        sa.CheckConstraint("word_budget >= 0",
                           name="ck_research_plan_sections_wb"),
        sa.CheckConstraint("budget_weight >= 0",
                           name="ck_research_plan_sections_bw"),
        sa.CheckConstraint(
            "evidence_coverage_target >= 0 AND "
            "evidence_coverage_target <= 1",
            name="ck_research_plan_sections_ect"),
    )
    op.create_index("ix_research_plan_sections_plan_order",
                    "research_plan_sections",
                    ["plan_id", "display_order"])

    op.create_table(
        "research_evidence_requirements",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("section_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("requirement_key", sa.Text(), nullable=False),
        sa.Column("requirement_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("min_sources", sa.Integer(), nullable=True),
        sa.Column("max_sources", sa.Integer(), nullable=True),
        sa.Column("preferred_paper_types", JSONB, nullable=True),
        sa.Column("preferred_research_designs", JSONB, nullable=True),
        sa.Column("max_age_years", sa.Integer(), nullable=True),
        sa.Column("full_text_required", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("min_relevance_score", sa.Numeric(), nullable=True),
        sa.Column("coverage_weight", sa.Numeric(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("requirement_meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["research_plans.id"], ondelete="CASCADE",
            name="fk_research_evidence_requirements_plan"),
        sa.ForeignKeyConstraint(
            ["section_id"], ["research_plan_sections.id"],
            ondelete="CASCADE",
            name="fk_research_evidence_requirements_section"),
        sa.UniqueConstraint("plan_id", "requirement_key",
                            name="ux_research_evidence_requirements_key"),
        sa.CheckConstraint("min_sources IS NULL OR min_sources >= 0",
                           name="ck_rer_min"),
        sa.CheckConstraint(
            "max_sources IS NULL OR "
            "(min_sources IS NOT NULL AND max_sources >= min_sources)",
            name="ck_rer_max_ge_min"),
        sa.CheckConstraint("priority >= 0", name="ck_rer_priority"),
        sa.CheckConstraint("coverage_weight >= 0", name="ck_rer_weight"),
        sa.CheckConstraint(
            "min_relevance_score IS NULL OR "
            "(min_relevance_score >= 0 AND min_relevance_score <= 1)",
            name="ck_rer_min_rel"),
    )
    op.create_index("ix_research_evidence_requirements_plan",
                    "research_evidence_requirements", ["plan_id"])
    op.create_index("ix_research_evidence_requirements_section",
                    "research_evidence_requirements", ["section_id"])

    op.create_table(
        "research_plan_dependencies",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("upstream_section_id", PGUUID(as_uuid=True),
                  nullable=False),
        sa.Column("downstream_section_id", PGUUID(as_uuid=True),
                  nullable=False),
        sa.Column("dependency_type", sa.Text(), nullable=False,
                  server_default=sa.text("'requires'")),
        sa.Column("dependency_meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["research_plans.id"], ondelete="CASCADE",
            name="fk_research_plan_dependencies_plan"),
        sa.ForeignKeyConstraint(
            ["upstream_section_id"], ["research_plan_sections.id"],
            ondelete="CASCADE",
            name="fk_research_plan_dependencies_upstream"),
        sa.ForeignKeyConstraint(
            ["downstream_section_id"], ["research_plan_sections.id"],
            ondelete="CASCADE",
            name="fk_research_plan_dependencies_downstream"),
        sa.UniqueConstraint(
            "plan_id", "upstream_section_id", "downstream_section_id",
            name="ux_research_plan_dependencies_edge"),
        sa.CheckConstraint(
            "dependency_type IN ('requires','informs','precedes')",
            name="ck_research_plan_dependencies_type"),
        sa.CheckConstraint(
            "upstream_section_id <> downstream_section_id",
            name="ck_research_plan_dependencies_no_self"),
    )
    op.create_index("ix_research_plan_dependencies_plan",
                    "research_plan_dependencies", ["plan_id"])

    op.create_table(
        "research_plan_runs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("planner_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("planning_mode", sa.Text(), nullable=False),
        sa.Column("llm_provider", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.Text(), nullable=True),
        sa.Column("input_snapshot", JSONB, nullable=True),
        sa.Column("output_summary", JSONB, nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_research_plan_runs_project"),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["research_plans.id"], ondelete="SET NULL",
            name="fk_research_plan_runs_plan"),
        sa.CheckConstraint(
            "status IN ('running','completed','failed','skipped')",
            name="ck_research_plan_runs_status"),
        sa.CheckConstraint(
            "planning_mode IN "
            "('deterministic','hybrid','deterministic_fallback')",
            name="ck_research_plan_runs_mode"),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_research_plan_runs_duration"),
    )
    op.create_index("ix_research_plan_runs_project",
                    "research_plan_runs", ["project_id"])
    op.create_index("ix_research_plan_runs_context",
                    "research_plan_runs", ["project_id", "context_hash"])
    op.create_index(
        "ux_research_plan_runs_completed",
        "research_plan_runs",
        ["project_id", "context_hash", "planner_version"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION research_plan_runs_no_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'research_plan_runs is append-only; '
                'UPDATE is forbidden';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_research_plan_runs_no_update
        BEFORE UPDATE ON research_plan_runs
        FOR EACH ROW EXECUTE FUNCTION research_plan_runs_no_update();
        """
    )

    op.drop_constraint(
        "ck_project_events_type", "project_events", type_="check"
    )
    op.create_check_constraint(
        "ck_project_events_type", "project_events", _EVENT_CHECK
    )


def downgrade() -> None:
    conn = op.get_bind()
    placeholders = ",".join(f"'{e}'" for e in _M24_EVENTS)
    count = conn.execute(
        sa.text(
            "SELECT count(*) FROM project_events "
            f"WHERE event_type IN ({placeholders})"
        )
    ).scalar() or 0
    if count:
        raise RuntimeError(
            f"Cannot downgrade to 0018: {count} M24 audit events exist. "
            "Refusing to purge immutable audit history."
        )

    op.drop_constraint(
        "ck_project_events_type", "project_events", type_="check"
    )
    op.create_check_constraint(
        "ck_project_events_type", "project_events",
        "event_type IN ("
        "'project_created','project_updated','project_archived',"
        "'classification_started','classification_completed',"
        "'classification_recomputed','classification_overridden',"
        "'classification_failed','classification_skipped',"
        "'literature_analysis_started','literature_analysis_completed',"
        "'literature_analysis_failed','literature_analysis_skipped',"
        "'literature_screening_overridden',"
        "'literature_cluster_completed','literature_gap_detected'"
        ")",
    )

    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_research_plan_runs_no_modify ON research_plan_runs"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS research_plan_runs_no_modify()"
    )
    for ix in (
        "ux_research_plan_runs_completed",
        "ix_research_plan_runs_context",
        "ix_research_plan_runs_project",
    ):
        op.drop_index(ix, table_name="research_plan_runs")
    op.drop_table("research_plan_runs")

    op.drop_index("ix_research_plan_dependencies_plan",
                  table_name="research_plan_dependencies")
    op.drop_table("research_plan_dependencies")

    op.drop_index("ix_research_evidence_requirements_section",
                  table_name="research_evidence_requirements")
    op.drop_index("ix_research_evidence_requirements_plan",
                  table_name="research_evidence_requirements")
    op.drop_table("research_evidence_requirements")

    op.drop_index("ix_research_plan_sections_plan_order",
                  table_name="research_plan_sections")
    op.drop_table("research_plan_sections")

    op.drop_index("ux_research_plans_context_completed",
                  table_name="research_plans")
    op.drop_index("ix_research_plans_project_version",
                  table_name="research_plans")
    op.drop_index("ix_research_plans_project_status",
                  table_name="research_plans")
    op.drop_index("ix_research_plans_project",
                  table_name="research_plans")
    op.drop_table("research_plans")