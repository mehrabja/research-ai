"""M30 — Citation Engine tables.

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-25

Non-destructive: creates new tables only.
No backfill, no reassignment of historical data.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


CLAIM_TYPES = (
    "background", "definition", "method", "result", "comparison",
    "causal", "limitation", "synthesis", "conclusion", "technical",
)
EVIDENCE_TYPES = (
    "m28_evidence", "m29_technical_fact",
    "m29_experiment_result", "m29_metric",
)
SUPPORT_LEVELS = (
    "supports", "partially_supports", "contradicts", "context_only",
)
RELATION_TYPES = (
    "supports", "partially_supports", "contradicts", "context_only",
    "methods_reference", "background_reference",
)
CITATION_STYLES = ("numeric", "author_year")
RUN_STATUSES = ("running", "completed", "failed", "skipped")
CLAIM_STATUSES = ("extracted", "mapped", "unsupported")


def upgrade() -> None:
    op.create_table(
        "citation_runs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "manuscript_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscripts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("m30_version", sa.Text(), nullable=False),
        sa.Column("citation_style", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "claim_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "citation_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "unsupported_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "mixed_support_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "duplicate_reference_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "coverage_score", sa.Numeric(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("output_summary", postgresql.JSONB(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.CheckConstraint(
            _in_check("status", RUN_STATUSES),
            name="ck_citation_runs_status",
        ),
        sa.CheckConstraint(
            _in_check("citation_style", CITATION_STYLES),
            name="ck_citation_runs_style",
        ),
        sa.CheckConstraint(
            "claim_count >= 0 AND citation_count >= 0 AND "
            "unsupported_count >= 0 AND mixed_support_count >= 0 AND "
            "duplicate_reference_count >= 0",
            name="ck_citation_runs_counts",
        ),
        sa.CheckConstraint(
            "coverage_score >= 0 AND coverage_score <= 1",
            name="ck_citation_runs_coverage",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_citation_runs_duration",
        ),
    )
    op.create_index(
        "ix_citation_runs_report", "citation_runs", ["report_id"],
    )
    op.create_index(
        "ix_citation_runs_context", "citation_runs",
        ["report_id", "manuscript_version_id", "context_hash",
         "m30_version", "citation_style"],
    )
    op.create_index(
        "ux_citation_runs_completed", "citation_runs",
        ["report_id", "manuscript_version_id", "context_hash",
         "m30_version", "citation_style"],
        unique=True,
        postgresql_where=sa.text("status = 'completed'"),
    )

    op.create_table(
        "claims",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "citation_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("citation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "manuscript_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "manuscript_section_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("claim_hash", sa.Text(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.Text(), nullable=False),
        sa.Column("location", postgresql.JSONB(), nullable=True),
        sa.Column("claim_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'extracted'"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("claim_type", CLAIM_TYPES), name="ck_claims_type",
        ),
        sa.CheckConstraint(
            _in_check("status", CLAIM_STATUSES), name="ck_claims_status",
        ),
        sa.UniqueConstraint(
            "citation_run_id", "claim_hash",
            name="ux_claims_run_hash",
        ),
    )
    op.create_index("ix_claims_run", "claims", ["citation_run_id"])
    op.create_index(
        "ix_claims_version_section", "claims",
        ["manuscript_version_id", "manuscript_section_id"],
    )

    op.create_table(
        "claim_evidence",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "claim_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column(
            "evidence_id", postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("support_level", sa.Text(), nullable=False),
        sa.Column(
            "relevance_score", sa.Numeric(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("evidence_type", EVIDENCE_TYPES),
            name="ck_claim_evidence_type",
        ),
        sa.CheckConstraint(
            _in_check("support_level", SUPPORT_LEVELS),
            name="ck_claim_evidence_support",
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_claim_evidence_relevance",
        ),
    )
    op.create_index(
        "ix_claim_evidence_claim", "claim_evidence", ["claim_id"],
    )
    op.create_index(
        "ix_claim_evidence_type_id", "claim_evidence",
        ["evidence_type", "evidence_id"],
    )

    op.create_table(
        "citation_identities",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("identity_key", sa.Text(), nullable=False),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("canonical_doi", sa.Text(), nullable=True),
        sa.Column("canonical_title", sa.Text(), nullable=True),
        sa.Column("canonical_first_author", sa.Text(), nullable=True),
        sa.Column("canonical_year", sa.Integer(), nullable=True),
        sa.Column("display_label", sa.Text(), nullable=True),
        sa.Column("normalization_version", sa.Text(), nullable=False),
        sa.Column("identity_meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint(
            "report_id", "identity_key",
            name="ux_citation_identities_report_key",
        ),
    )
    op.create_index(
        "ix_citation_identities_report", "citation_identities",
        ["report_id"],
    )
    op.create_index(
        "ix_citation_identities_source", "citation_identities",
        ["source_id"],
    )

    op.create_table(
        "claim_citations",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "claim_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "citation_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("citation_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("support_level", sa.Text(), nullable=False),
        sa.Column(
            "relevance_score", sa.Numeric(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column("sentence_index", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("citation_order", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("relation_type", RELATION_TYPES),
            name="ck_claim_citations_relation",
        ),
        sa.CheckConstraint(
            _in_check("support_level", SUPPORT_LEVELS),
            name="ck_claim_citations_support",
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_claim_citations_relevance",
        ),
        sa.CheckConstraint(
            "paragraph_index IS NULL OR paragraph_index >= 0",
            name="ck_claim_citations_paragraph",
        ),
        sa.CheckConstraint(
            "sentence_index IS NULL OR sentence_index >= 0",
            name="ck_claim_citations_sentence",
        ),
        sa.CheckConstraint(
            "char_start IS NULL OR char_end IS NULL "
            "OR char_end >= char_start",
            name="ck_claim_citations_char_range",
        ),
        sa.CheckConstraint(
            "citation_order IS NULL OR citation_order >= 1",
            name="ck_claim_citations_order",
        ),
        sa.UniqueConstraint(
            "claim_id", "citation_id",
            name="ux_claim_citations_pair",
        ),
    )
    op.create_index(
        "ix_claim_citations_claim", "claim_citations", ["claim_id"],
    )
    op.create_index(
        "ix_claim_citations_citation", "claim_citations",
        ["citation_id"],
    )
    op.create_index(
        "ix_claim_citations_placement", "claim_citations",
        ["claim_id", "paragraph_index", "sentence_index", "char_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_claim_citations_placement", table_name="claim_citations",
    )
    op.drop_index(
        "ix_claim_citations_citation", table_name="claim_citations",
    )
    op.drop_index(
        "ix_claim_citations_claim", table_name="claim_citations",
    )
    op.drop_table("claim_citations")

    op.drop_index(
        "ix_citation_identities_source", table_name="citation_identities",
    )
    op.drop_index(
        "ix_citation_identities_report", table_name="citation_identities",
    )
    op.drop_table("citation_identities")

    op.drop_index(
        "ix_claim_evidence_type_id", table_name="claim_evidence",
    )
    op.drop_index("ix_claim_evidence_claim", table_name="claim_evidence")
    op.drop_table("claim_evidence")

    op.drop_index("ix_claims_version_section", table_name="claims")
    op.drop_index("ix_claims_run", table_name="claims")
    op.drop_table("claims")

    op.drop_index(
        "ux_citation_runs_completed", table_name="citation_runs",
    )
    op.drop_index("ix_citation_runs_context", table_name="citation_runs")
    op.drop_index("ix_citation_runs_report", table_name="citation_runs")
    op.drop_table("citation_runs")