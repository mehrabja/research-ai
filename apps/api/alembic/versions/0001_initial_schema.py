"""Initial foundational schema for research-ai.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00

Design notes
------------
* Extensions pgcrypto and vector are installed here, not on the host.
* All UUID PKs use gen_random_uuid() as a server default.
* All timestamps are TIMESTAMPTZ.
* All monetary amounts are NUMERIC(18, 8). Never FLOAT.
* Status columns are TEXT + CHECK so new states can be added without
  destructive migrations.
* Historical / audit tables are ON DELETE RESTRICT toward reports/users.
* Ephemeral owned children cascade from their parent.
* Vector columns use a single fixed dimension (1536). Mixing dimensions
  in one column is not supported; changing this requires migration +
  re-embedding + index rebuild. See docs/database/README.md.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMBEDDING_DIM = 1536

REPORT_STATUSES = (
    "draft", "searching", "extracting", "retrieving", "generating",
    "review_1", "detecting", "humanizing", "translating",
    "post_translation_review", "converging", "review_2", "validating",
    "completed", "failed", "cancelled",
)
SOURCE_STATUSES = (
    "metadata_only", "abstract_only", "full_text",
    "structured_full_text", "extraction_failed",
)
RUN_STATUSES_COMMON = ("pending", "running", "success", "failed", "cancelled")
DETECTION_STATUSES = ("pending", "running", "success", "partial", "failed")
TRANSLATION_STATUSES = ("pending", "running", "success", "partial", "failed")
HUMANIZATION_STATUSES = ("running", "success", "partial", "budget_exceeded", "failed")
CONVERGENCE_STATUSES = (
    "running", "converged", "max_iterations_reached", "plateau_detected",
    "budget_exceeded", "failed", "stopped",
)
JOB_STATUSES = ("pending", "running", "success", "failed", "cancelled", "retrying")
REVIEW_STAGES = ("pre_translation", "post_translation")
REVIEW_ACTIONS = ("edited", "approved", "rejected", "requested_changes")
CREDIT_TYPES = ("purchase", "reserve", "settlement", "release", "refund")
CREDIT_STATUSES = ("pending", "posted", "failed", "reversed")
SUPPORT_TYPES = ("direct", "synthesis")
ENTAILMENTS = ("supported", "contradicted", "unclear")
VALIDATION_STATUSES = ("pending", "passed", "failed", "needs_review")


# ---------------------------------------------------------------------------
# Column helpers
# ---------------------------------------------------------------------------
def _pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def _ts_pair() -> list[sa.Column]:
    return [_created_at(), _updated_at()]


def _uuid_fk(target: str, ondelete: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
    )


def _in_check(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"{column} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


def upgrade() -> None:
    # -------------------------------------------------------------------
    # Extensions
    # -------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ===================================================================
    # users
    # ===================================================================
    op.create_table(
        "users",
        _pk(),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_ts_pair(),
    )
    op.create_index(
        "ux_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )

    # ===================================================================
    # reports
    # ===================================================================
    op.create_table(
        "reports",
        _pk(),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("failed_at_phase", sa.Text(), nullable=True),
        sa.Column("tone", sa.Text(), nullable=True),
        sa.Column("length", sa.Text(), nullable=True),
        sa.Column("structure_template", sa.Text(), nullable=True),
        sa.Column("output_language", sa.Text(), nullable=False),
        sa.Column("audience_level", sa.Text(), nullable=True),
        *_ts_pair(),
        _in_check("status", REPORT_STATUSES, "ck_reports_status"),
    )
    op.create_index("ix_reports_user_id_created_at", "reports", ["user_id", "created_at"])
    op.create_index("ix_reports_status", "reports", ["status"])

    # ===================================================================
    # sources
    # ===================================================================
    op.create_table(
        "sources",
        _pk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("authors", postgresql.JSONB(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("doi", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("source_api", sa.Text(), nullable=True),
        sa.Column("external_source_id", sa.Text(), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source_quality", sa.Numeric(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        *_ts_pair(),
        _in_check("status", SOURCE_STATUSES, "ck_sources_status"),
        sa.CheckConstraint("year IS NULL OR (year >= 1000 AND year <= 2200)", name="ck_sources_year"),
        sa.CheckConstraint("citation_count IS NULL OR citation_count >= 0", name="ck_sources_citation_count"),
        sa.CheckConstraint(
            "source_quality IS NULL OR (source_quality >= 0 AND source_quality <= 1)",
            name="ck_sources_quality_range",
        ),
    )
    op.create_index("ix_sources_report_id", "sources", ["report_id"])
    op.create_index("ix_sources_doi", "sources", ["doi"])
    op.create_index(
        "ix_sources_source_api_external_id",
        "sources",
        ["source_api", "external_source_id"],
    )
    op.create_index("ix_sources_status", "sources", ["status"])

    # ===================================================================
    # chunks
    # ===================================================================
    op.create_table(
        "chunks",
        _pk(),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("embedding_model_version", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        _created_at(),
        sa.UniqueConstraint("source_id", "chunk_index", name="ux_chunks_source_index"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_chunks_index_nonneg"),
        sa.CheckConstraint(
            "token_count IS NULL OR token_count >= 0",
            name="ck_chunks_token_count_nonneg",
        ),
    )
    op.create_index("ix_chunks_source_id_chunk_index", "chunks", ["source_id", "chunk_index"])
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
    )

    # ===================================================================
    # generation_runs
    # ===================================================================
    op.create_table(
        "generation_runs",
        _pk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("model_provider", sa.Text(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("input_token_count", sa.Integer(), nullable=True),
        sa.Column("output_token_count", sa.Integer(), nullable=True),
        sa.Column("output_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _in_check("status", ("pending", "running", "success", "failed", "cancelled"), "ck_generation_runs_status"),
        sa.CheckConstraint(
            "input_token_count IS NULL OR input_token_count >= 0",
            name="ck_generation_runs_input_tokens",
        ),
        sa.CheckConstraint(
            "output_token_count IS NULL OR output_token_count >= 0",
            name="ck_generation_runs_output_tokens",
        ),
    )
    op.create_index("ix_generation_runs_report_created", "generation_runs", ["report_id", "created_at"])

    # ===================================================================
    # citation_links (depends on generation_runs, sources, chunks)
    # ===================================================================
    op.create_table(
        "citation_links",
        _pk(),
        sa.Column(
            "generation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("support_type", sa.Text(), nullable=False),
        sa.Column("similarity_score", sa.Numeric(), nullable=True),
        sa.Column("entailment_check", sa.Text(), nullable=True),
        sa.Column("numeric_entity_check", postgresql.JSONB(), nullable=True),
        sa.Column(
            "validation_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        _created_at(),
        _in_check("support_type", SUPPORT_TYPES, "ck_citation_links_support_type"),
        sa.CheckConstraint(
            "entailment_check IS NULL OR entailment_check IN ('supported','contradicted','unclear')",
            name="ck_citation_links_entailment",
        ),
        _in_check("validation_status", VALIDATION_STATUSES, "ck_citation_links_validation_status"),
    )
    op.create_index("ix_citation_links_generation_run", "citation_links", ["generation_run_id"])
    op.create_index("ix_citation_links_source", "citation_links", ["source_id"])
    op.create_index("ix_citation_links_validation_status", "citation_links", ["validation_status"])

    # ===================================================================
    # detection_runs / detection_segments
    # ===================================================================
    op.create_table(
        "detection_runs",
        _pk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "generation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scanned_text_version", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("overall_score", sa.Numeric(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        _created_at(),
        _in_check("status", DETECTION_STATUSES, "ck_detection_runs_status"),
    )
    op.create_index("ix_detection_runs_report_created", "detection_runs", ["report_id", "created_at"])

    op.create_table(
        "detection_segments",
        _pk(),
        sa.Column(
            "detection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("detection_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column("segment_identifier", sa.Text(), nullable=True),
        sa.Column("score", sa.Numeric(), nullable=True),
        sa.Column("flagged", sa.Boolean(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "paragraph_index IS NULL OR paragraph_index >= 0",
            name="ck_detection_segments_paragraph_index",
        ),
    )
    op.create_index("ix_detection_segments_run", "detection_segments", ["detection_run_id"])

    # ===================================================================
    # translation_runs / translation_versions
    # ===================================================================
    op.create_table(
        "translation_runs",
        _pk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "generation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_lang", sa.Text(), nullable=False),
        sa.Column("target_lang", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _in_check("status", TRANSLATION_STATUSES, "ck_translation_runs_status"),
    )
    op.create_index("ix_translation_runs_report_created", "translation_runs", ["report_id", "created_at"])

    op.create_table(
        "translation_versions",
        _pk(),
        sa.Column(
            "translation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("translation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("preservation_check_status", sa.Text(), nullable=False),
        sa.Column("preservation_details", postgresql.JSONB(), nullable=True),
        _created_at(),
    )
    op.create_index("ix_translation_versions_run", "translation_versions", ["translation_run_id"])

    # ===================================================================
    # humanization_runs / iterations / rewrites
    # ===================================================================
    op.create_table(
        "humanization_runs",
        _pk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "generation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "translation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("translation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("policy_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("detection_score_before", sa.Numeric(), nullable=True),
        sa.Column("detection_score_after", sa.Numeric(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "stage IN ('pre_translation','post_translation')",
            name="ck_humanization_runs_stage",
        ),
        _in_check("status", HUMANIZATION_STATUSES, "ck_humanization_runs_status"),
        sa.CheckConstraint(
            "tokens_used IS NULL OR tokens_used >= 0",
            name="ck_humanization_runs_tokens",
        ),
    )
    op.create_index("ix_humanization_runs_report_stage", "humanization_runs", ["report_id", "stage"])

    op.create_table(
        "humanization_iterations",
        _pk(),
        sa.Column(
            "humanization_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("humanization_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("iteration_index", sa.Integer(), nullable=False),
        sa.Column("detection_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("flagged_segments", postgresql.JSONB(), nullable=True),
        sa.Column("rewritten_segments", postgresql.JSONB(), nullable=True),
        sa.Column("detection_score_mean", sa.Numeric(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 8), nullable=True),
        _created_at(),
        sa.UniqueConstraint(
            "humanization_run_id",
            "iteration_index",
            name="ux_humanization_iterations_run_index",
        ),
        sa.CheckConstraint("iteration_index >= 0", name="ck_humanization_iterations_index"),
    )
    op.create_index(
        "ix_humanization_iterations_run_index",
        "humanization_iterations",
        ["humanization_run_id", "iteration_index"],
    )

    op.create_table(
        "humanization_rewrites",
        _pk(),
        sa.Column(
            "humanization_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("humanization_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "iteration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("humanization_iterations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("segment_id", sa.Text(), nullable=False),
        sa.Column("layer", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("text_before", sa.Text(), nullable=True),
        sa.Column("text_after", sa.Text(), nullable=True),
        sa.Column("preservation_ok", sa.Boolean(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True, unique=True),
        _created_at(),
    )
    op.create_index("ix_humanization_rewrites_run", "humanization_rewrites", ["humanization_run_id"])
    op.create_index("ix_humanization_rewrites_iteration", "humanization_rewrites", ["iteration_id"])

    # ===================================================================
    # convergence
    # ===================================================================
    op.create_table(
        "convergence_runs",
        _pk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "humanization_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("humanization_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("target_threshold", sa.Numeric(), nullable=False, server_default=sa.text("0.25")),
        sa.Column("policy_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("initial_score", sa.Numeric(), nullable=True),
        sa.Column("final_score", sa.Numeric(), nullable=True),
        sa.Column("best_score", sa.Numeric(), nullable=True),
        sa.Column("best_iteration_index", sa.Integer(), nullable=True),
        sa.Column("iterations_executed", sa.Integer(), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("total_duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "needs_human_attention",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _in_check("status", CONVERGENCE_STATUSES, "ck_convergence_runs_status"),
    )
    op.create_index("ix_convergence_runs_report_created", "convergence_runs", ["report_id", "created_at"])

    op.create_table(
        "convergence_iterations",
        _pk(),
        sa.Column(
            "convergence_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("convergence_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("iteration_index", sa.Integer(), nullable=False),
        sa.Column("strategy_name", sa.Text(), nullable=False),
        sa.Column("score_before", sa.Numeric(), nullable=False),
        sa.Column("score_after", sa.Numeric(), nullable=False),
        sa.Column("improvement", sa.Numeric(), nullable=True),
        sa.Column("flagged_segment_ids", postgresql.JSONB(), nullable=True),
        sa.Column("rewritten_segment_ids", postgresql.JSONB(), nullable=True),
        sa.Column(
            "preservation_failures",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("detection_snapshot", postgresql.JSONB(), nullable=True),
        _created_at(),
        sa.UniqueConstraint(
            "convergence_run_id",
            "iteration_index",
            name="ux_convergence_iterations_run_index",
        ),
        sa.CheckConstraint("iteration_index >= 0", name="ck_convergence_iterations_index"),
    )
    op.create_index(
        "ix_convergence_iterations_run_index",
        "convergence_iterations",
        ["convergence_run_id", "iteration_index"],
    )

    op.create_table(
        "convergence_best_snapshots",
        _pk(),
        sa.Column(
            "convergence_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("convergence_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("iteration_index", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=False),
        sa.Column("segments_json", postgresql.JSONB(), nullable=False),
        _created_at(),
    )

    op.create_table(
        "convergence_strategies",
        _pk(),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("temperature", sa.Numeric(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("techniques", postgresql.JSONB(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Text(), nullable=False, server_default=sa.text("'1.0.0'")),
        *_ts_pair(),
    )
    op.create_index(
        "ix_convergence_strategies_active_order",
        "convergence_strategies",
        ["active", "order_index"],
    )

    # ===================================================================
    # knowledge tables
    # ===================================================================
    op.create_table(
        "voice_profiles",
        _pk(),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("formality", sa.Numeric(), nullable=True),
        sa.Column("avg_sentence_length", sa.Numeric(), nullable=True),
        sa.Column("sentence_length_variance", sa.Numeric(), nullable=True),
        sa.Column("active_ratio", sa.Numeric(), nullable=True),
        sa.Column("first_person", sa.Text(), nullable=True),
        sa.Column("nominalization_tolerance", sa.Numeric(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "language", name="ux_voice_profiles_user_lang"),
    )

    op.create_table(
        "style_exemplars",
        _pk(),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("human_score", sa.Numeric(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "license IS NULL OR length(license) > 0",
            name="ck_style_exemplars_license_present",
        ),
    )
    op.create_index("ix_style_exemplars_domain_language", "style_exemplars", ["domain", "language"])
    op.execute(
        "CREATE INDEX ix_style_exemplars_embedding_hnsw ON style_exemplars "
        "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
    )

    op.create_table(
        "ai_tell_patterns",
        _pk(),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("replacement_pool", postgresql.JSONB(), nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Text(), nullable=False, server_default=sa.text("'1.0.0'")),
        *_ts_pair(),
        sa.CheckConstraint("severity >= 0 AND severity <= 10", name="ck_ai_tell_patterns_severity"),
    )
    op.create_index("ix_ai_tell_patterns_language_active", "ai_tell_patterns", ["language", "active"])
    op.create_index("ix_ai_tell_patterns_domain_active", "ai_tell_patterns", ["domain", "active"])

    op.create_table(
        "detection_thresholds",
        _pk(),
        sa.Column("detector", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("threshold", sa.Numeric(), nullable=False),
        sa.Column("calibration_set_size", sa.Integer(), nullable=True),
        sa.Column("percentiles", postgresql.JSONB(), nullable=True),
        sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "detector", "domain", "language",
            name="ux_detection_thresholds_detector_domain_lang",
        ),
        sa.CheckConstraint("threshold >= 0 AND threshold <= 1", name="ck_detection_thresholds_range"),
    )

    op.create_table(
        "terminology_glossary",
        _pk(),
        sa.Column("source_term", sa.Text(), nullable=False),
        sa.Column("target_term", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("language_pair", sa.Text(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_ts_pair(),
    )
    op.create_index(
        "ix_terminology_glossary_domain_lang_pair",
        "terminology_glossary",
        ["domain", "language_pair"],
    )
    op.create_index("ix_terminology_glossary_locked", "terminology_glossary", ["locked"])

    # ===================================================================
    # report_versions / review_events
    # ===================================================================
    op.create_table(
        "report_versions",
        _pk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "source_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("report_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_by_user", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("change_type", sa.Text(), nullable=True),
        sa.Column("diff_from_previous", postgresql.JSONB(), nullable=True),
        _created_at(),
        sa.UniqueConstraint(
            "report_id", "version_number", "language",
            name="ux_report_versions_report_version_lang",
        ),
    )
    op.create_index(
        "ix_report_versions_report_lang_version",
        "report_versions",
        ["report_id", "language", "version_number"],
    )

    op.create_table(
        "review_events",
        _pk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("report_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        _created_at(),
        _in_check("stage", REVIEW_STAGES, "ck_review_events_stage"),
        _in_check("action", REVIEW_ACTIONS, "ck_review_events_action"),
    )
    op.create_index("ix_review_events_report_created", "review_events", ["report_id", "created_at"])

    # ===================================================================
    # ops tables
    # ===================================================================
    op.create_table(
        "jobs",
        _pk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True, unique=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _in_check("status", JOB_STATUSES, "ck_jobs_status"),
        sa.CheckConstraint("retry_count >= 0", name="ck_jobs_retry_count"),
    )
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at"])
    op.create_index("ix_jobs_report", "jobs", ["report_id"])
    op.create_index("ix_jobs_trace_id", "jobs", ["trace_id"])

    op.create_table(
        "usage_logs",
        _pk(),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Intentionally SET NULL: usage history must survive report deletion
        # or anonymization. The row remains as an anonymous billing artifact.
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd_raw", sa.Numeric(18, 8), nullable=True),
        sa.Column("cost_usd_charged", sa.Numeric(18, 8), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True, unique=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_usage_logs_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_usage_logs_output_tokens",
        ),
    )
    op.create_index("ix_usage_logs_user_created", "usage_logs", ["user_id", "created_at"])
    op.create_index("ix_usage_logs_report_created", "usage_logs", ["report_id", "created_at"])
    op.create_index("ix_usage_logs_trace_id", "usage_logs", ["trace_id"])

    op.create_table(
        "model_pricing",
        _pk(),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("output_price", sa.Numeric(18, 8), nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_model_pricing_effective_range",
        ),
    )
    op.create_index(
        "ix_model_pricing_provider_model_effective_from",
        "model_pricing",
        ["provider", "model", "effective_from"],
    )

    op.create_table(
        "credit_transactions",
        _pk(),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 8), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'posted'")),
        _created_at(),
        _in_check("type", CREDIT_TYPES, "ck_credit_transactions_type"),
        _in_check("status", CREDIT_STATUSES, "ck_credit_transactions_status"),
        sa.CheckConstraint("amount >= 0", name="ck_credit_transactions_amount_nonneg"),
    )
    op.create_index("ix_credit_transactions_user_created", "credit_transactions", ["user_id", "created_at"])
    op.create_index("ix_credit_transactions_reference", "credit_transactions", ["reference"])


def downgrade() -> None:
    """Drop everything created by this migration.

    Destructive. Development only. Extensions are intentionally NOT
    dropped because other schemas may share them.
    """
    op.drop_table("credit_transactions")
    op.drop_table("model_pricing")
    op.drop_table("usage_logs")
    op.drop_table("jobs")
    op.drop_table("review_events")
    op.drop_table("report_versions")
    op.drop_table("terminology_glossary")
    op.drop_table("detection_thresholds")
    op.drop_table("ai_tell_patterns")
    op.drop_table("style_exemplars")
    op.drop_table("voice_profiles")
    op.drop_table("convergence_strategies")
    op.drop_table("convergence_best_snapshots")
    op.drop_table("convergence_iterations")
    op.drop_table("convergence_runs")
    op.drop_table("humanization_rewrites")
    op.drop_table("humanization_iterations")
    op.drop_table("humanization_runs")
    op.drop_table("translation_versions")
    op.drop_table("translation_runs")
    op.drop_table("detection_segments")
    op.drop_table("detection_runs")
    op.drop_table("citation_links")
    op.drop_table("generation_runs")
    op.drop_table("chunks")
    op.drop_table("sources")
    op.drop_table("reports")
    op.drop_index("ux_users_email_lower", table_name="users")
    op.drop_table("users")
