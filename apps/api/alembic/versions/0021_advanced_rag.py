"""M26 — Advanced RAG & Research Memory schema.

Revision ID: 0021
Revises: 0020
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

_RUN_STATUSES = ("running", "completed", "failed", "skipped")
_MEMORY_TYPES = (
    "query_result", "useful_source", "useful_chunk",
    "evidence_pattern", "research_theme", "retrieval_summary",
)
_MEMORY_STATUSES = ("active", "superseded", "archived")


def _in_clause(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "retrieval_runs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("report_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("research_plan_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("plan_section_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("evidence_requirement_id", PGUUID(as_uuid=True),
                  nullable=True),
        sa.Column("graph_version_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("query_hash", sa.Text(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("retrieval_version", sa.Text(), nullable=False),
        sa.Column("ranking_model_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("final_result_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("input_snapshot", JSONB, nullable=True),
        sa.Column("output_summary", JSONB, nullable=True),
        sa.Column("coverage", JSONB, nullable=True),
        sa.Column("warnings", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_retrieval_runs_project"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="SET NULL",
            name="fk_retrieval_runs_user"),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], ondelete="SET NULL",
            name="fk_retrieval_runs_report"),
        sa.ForeignKeyConstraint(
            ["research_plan_id"], ["research_plans.id"],
            ondelete="SET NULL", name="fk_retrieval_runs_plan"),
        sa.ForeignKeyConstraint(
            ["graph_version_id"], ["knowledge_graph_versions.id"],
            ondelete="SET NULL", name="fk_retrieval_runs_graph"),
        sa.CheckConstraint(
            _in_clause("status", _RUN_STATUSES),
            name="ck_retrieval_runs_status"),
        sa.CheckConstraint(
            "candidate_count >= 0 AND final_result_count >= 0",
            name="ck_retrieval_runs_counts"),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_retrieval_runs_duration"),
    )
    op.create_index("ix_retrieval_runs_project",
                    "retrieval_runs", ["project_id"])
    op.create_index("ix_retrieval_runs_project_context",
                    "retrieval_runs", ["project_id", "context_hash"])
    op.create_index("ix_retrieval_runs_project_query",
                    "retrieval_runs", ["project_id", "query_hash"])
    op.create_index(
        "ux_retrieval_runs_completed", "retrieval_runs",
        ["project_id", "context_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"))

    op.create_table(
        "retrieval_results",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("retrieval_run_id", PGUUID(as_uuid=True),
                  nullable=False),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("source_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("vector_score", sa.Numeric(), nullable=True),
        sa.Column("lexical_score", sa.Numeric(), nullable=True),
        sa.Column("graph_score", sa.Numeric(), nullable=True),
        sa.Column("memory_score", sa.Numeric(), nullable=True),
        sa.Column("quality_score", sa.Numeric(), nullable=True),
        sa.Column("diversity_penalty", sa.Numeric(), nullable=True),
        sa.Column("final_score", sa.Numeric(), nullable=False),
        sa.Column("retrieval_stage", sa.Text(), nullable=False),
        sa.Column("retrieval_reason", JSONB, nullable=False),
        sa.Column("graph_distance", sa.Integer(), nullable=True),
        sa.Column("memory_match", PGUUID(as_uuid=True), nullable=True),
        sa.Column("result_meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["retrieval_run_id"], ["retrieval_runs.id"],
            ondelete="CASCADE", name="fk_retrieval_results_run"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_retrieval_results_project"),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["chunks.id"], ondelete="CASCADE",
            name="fk_retrieval_results_chunk"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="CASCADE",
            name="fk_retrieval_results_source"),
        sa.CheckConstraint("rank >= 1", name="ck_retrieval_results_rank"),
        sa.UniqueConstraint(
            "retrieval_run_id", "rank",
            name="ux_retrieval_results_run_rank"),
    )
    op.create_index("ix_retrieval_results_run",
                    "retrieval_results", ["retrieval_run_id", "rank"])
    op.create_index("ix_retrieval_results_project_source",
                    "retrieval_results", ["project_id", "source_id"])
    op.create_index("ix_retrieval_results_project_chunk",
                    "retrieval_results", ["project_id", "chunk_id"])

    op.create_table(
        "research_memories",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("memory_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False,
                  server_default=sa.text("'active'")),
        sa.Column("content_fingerprint", sa.Text(), nullable=False),
        sa.Column("canonical_entity_type", sa.Text(), nullable=True),
        sa.Column("canonical_entity_id", PGUUID(as_uuid=True),
                  nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("importance", sa.Numeric(), nullable=False,
                  server_default=sa.text("0.5")),
        sa.Column("confidence", sa.Numeric(), nullable=False,
                  server_default=sa.text("0.5")),
        sa.Column("source_run_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("superseded_by_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("memory_meta", JSONB, nullable=True),
        sa.Column("reuse_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_research_memories_project"),
        sa.ForeignKeyConstraint(
            ["source_run_id"], ["retrieval_runs.id"],
            ondelete="SET NULL", name="fk_research_memories_run"),
        sa.ForeignKeyConstraint(
            ["superseded_by_id"], ["research_memories.id"],
            ondelete="SET NULL",
            name="fk_research_memories_superseded_by"),
        sa.CheckConstraint(
            _in_clause("memory_type", _MEMORY_TYPES),
            name="ck_research_memories_type"),
        sa.CheckConstraint(
            _in_clause("status", _MEMORY_STATUSES),
            name="ck_research_memories_status"),
        sa.CheckConstraint(
            "importance >= 0 AND importance <= 1",
            name="ck_research_memories_importance"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_research_memories_confidence"),
        sa.CheckConstraint(
            "reuse_count >= 0",
            name="ck_research_memories_reuse_count"),
        sa.UniqueConstraint(
            "project_id", "memory_type", "content_fingerprint",
            name="ux_research_memories_project_type_fp"),
    )
    op.create_index("ix_research_memories_project",
                    "research_memories", ["project_id"])
    op.create_index("ix_research_memories_project_type_status",
                    "research_memories",
                    ["project_id", "memory_type", "status"])
    op.create_index("ix_research_memories_project_entity",
                    "research_memories",
                    ["project_id", "canonical_entity_type",
                     "canonical_entity_id"])
    op.create_index("ix_research_memories_source_run",
                    "research_memories", ["source_run_id"])

    op.create_table(
        "research_memory_links",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("memory_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("linked_entity_type", sa.Text(), nullable=False),
        sa.Column("linked_entity_id", PGUUID(as_uuid=True),
                  nullable=False),
        sa.Column("relation", sa.Text(), nullable=False,
                  server_default=sa.text("'references'")),
        sa.Column("weight", sa.Numeric(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["memory_id"], ["research_memories.id"],
            ondelete="CASCADE", name="fk_research_memory_links_memory"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_research_memory_links_project"),
        sa.CheckConstraint(
            "weight >= 0", name="ck_research_memory_links_weight"),
        sa.UniqueConstraint(
            "memory_id", "linked_entity_type",
            "linked_entity_id", "relation",
            name="ux_research_memory_links_unique"),
    )
    op.create_index("ix_research_memory_links_memory",
                    "research_memory_links", ["memory_id"])
    op.create_index("ix_research_memory_links_project_entity",
                    "research_memory_links",
                    ["project_id", "linked_entity_type",
                     "linked_entity_id"])


def downgrade() -> None:
    conn = op.get_bind()
    total = 0
    for tbl in ("retrieval_results", "research_memory_links",
                "research_memories", "retrieval_runs"):
        rows = conn.execute(
            sa.text(f"SELECT count(*) FROM {tbl}")
        ).scalar() or 0
        total += int(rows)
    if total:
        raise RuntimeError(
            f"Cannot downgrade to 0020: {total} M26 rows exist."
        )

    for ix in (
        "ix_research_memory_links_project_entity",
        "ix_research_memory_links_memory",
    ):
        op.drop_index(ix, table_name="research_memory_links")
    op.drop_table("research_memory_links")

    for ix in (
        "ix_research_memories_source_run",
        "ix_research_memories_project_entity",
        "ix_research_memories_project_type_status",
        "ix_research_memories_project",
    ):
        op.drop_index(ix, table_name="research_memories")
    op.drop_table("research_memories")

    for ix in (
        "ix_retrieval_results_project_chunk",
        "ix_retrieval_results_project_source",
        "ix_retrieval_results_run",
    ):
        op.drop_index(ix, table_name="retrieval_results")
    op.drop_table("retrieval_results")

    for ix in (
        "ux_retrieval_runs_completed",
        "ix_retrieval_runs_project_query",
        "ix_retrieval_runs_project_context",
        "ix_retrieval_runs_project",
    ):
        op.drop_index(ix, table_name="retrieval_runs")
    op.drop_table("retrieval_runs")