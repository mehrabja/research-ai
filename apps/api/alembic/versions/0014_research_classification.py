"""M21 — Research classification.

Revision ID: 0014
Revises: 0013
"""
from __future__ import annotations

import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

TAXONOMY_VERSION = "m21.1"
_NS = uuid.UUID("6f8c4a86-5d33-4b9d-8e1f-3a4b5c6d7e8f")


def _du(code: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"domain:{code}")


def _pu(code: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"paper_type:{code}")


def _ru(code: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"research_design:{code}")


_DOMAINS: tuple[tuple[str, str, str | None, int, list[str]], ...] = (
    ("computer_science", "Computer Science", None, 0,
     ["cs", "computing", "informatics"]),
    ("artificial_intelligence", "Artificial Intelligence",
     "computer_science", 1, ["ai"]),
    ("natural_language_processing", "Natural Language Processing",
     "artificial_intelligence", 2, ["nlp", "natural language"]),
    ("machine_learning", "Machine Learning",
     "artificial_intelligence", 2, ["ml"]),
    ("software_engineering", "Software Engineering",
     "computer_science", 1, ["se"]),
    ("databases", "Databases", "computer_science", 1,
     ["database systems", "data management"]),
    ("medicine", "Medicine", None, 0, ["medical", "clinical medicine"]),
    ("cardiology", "Cardiology", "medicine", 1, []),
    ("oncology", "Oncology", "medicine", 1, ["cancer research"]),
    ("clinical_research", "Clinical Research", "medicine", 1,
     ["clinical trials"]),
    ("biology", "Biology", None, 0, ["life sciences"]),
    ("genetics", "Genetics", "biology", 1, ["genomics"]),
    ("ecology", "Ecology", "biology", 1, []),
    ("physics", "Physics", None, 0, []),
    ("condensed_matter", "Condensed Matter Physics", "physics", 1, []),
    ("mathematics", "Mathematics", None, 0, ["math"]),
    ("statistics", "Statistics", "mathematics", 1,
     ["statistical science"]),
    ("social_sciences", "Social Sciences", None, 0, ["social science"]),
    ("psychology", "Psychology", "social_sciences", 1, []),
    ("economics", "Economics", "social_sciences", 1, ["econ"]),
    ("engineering", "Engineering", None, 0, []),
    ("electrical_engineering", "Electrical Engineering",
     "engineering", 1, ["ee"]),
    ("chemistry", "Chemistry", None, 0, []),
    ("earth_sciences", "Earth Sciences", None, 0,
     ["geoscience", "geology"]),
)


_DESIGNS: tuple[tuple[str, str, list[str]], ...] = (
    ("experimental", "Experimental", []),
    ("observational", "Observational", []),
    ("randomized_controlled_trial", "Randomized Controlled Trial",
     ["randomised controlled trial", "rct"]),
    ("quasi_experimental", "Quasi-Experimental",
     ["quasi experimental"]),
    ("cohort", "Cohort", ["cohort study"]),
    ("case_control", "Case-Control", ["case control"]),
    ("cross_sectional", "Cross-Sectional", ["cross sectional"]),
    ("case_report", "Case Report", []),
    ("case_series", "Case Series", []),
    ("systematic_review", "Systematic Review", []),
    ("scoping_review", "Scoping Review", []),
    ("narrative_review", "Narrative Review", ["literature review"]),
    ("meta_analysis", "Meta-Analysis", ["meta analysis"]),
    ("qualitative", "Qualitative",
     ["qualitative study", "thematic analysis", "grounded theory"]),
    ("mixed_methods", "Mixed Methods", ["mixed-methods"]),
    ("survey", "Survey", ["questionnaire"]),
    ("simulation", "Simulation", ["monte carlo"]),
    ("benchmark", "Benchmark", ["benchmarking"]),
    ("dataset_description", "Dataset Description", ["dataset"]),
    ("method_development", "Method Development",
     ["method development", "new method", "novel method"]),
    ("theoretical", "Theoretical",
     ["theoretical model", "mathematical proof"]),
    ("computational", "Computational", ["computational model"]),
    ("unknown", "Unknown", []),
)


_PAPER_TYPES: tuple[tuple[str, str, list[str], str | None], ...] = (
    ("original_research", "Original Research",
     ["original article", "original research paper"], None),
    ("systematic_review", "Systematic Review",
     ["systematic literature review", "prisma review"],
     "systematic_review"),
    ("scoping_review", "Scoping Review", [], "scoping_review"),
    ("narrative_review", "Narrative Review",
     ["literature review"], "narrative_review"),
    ("meta_analysis", "Meta-Analysis",
     ["meta analysis", "pooled analysis"], "meta_analysis"),
    ("methodology_paper", "Methodology Paper",
     ["methods paper"], "method_development"),
    ("technical_paper", "Technical Paper",
     ["technical report"], None),
    ("theoretical_paper", "Theoretical Paper",
     ["theoretical analysis"], "theoretical"),
    ("case_report", "Case Report", [], "case_report"),
    ("case_series", "Case Series", [], "case_series"),
    ("cohort_study", "Cohort Study", ["cohort analysis"], "cohort"),
    ("case_control_study", "Case-Control Study",
     ["case control study"], "case_control"),
    ("cross_sectional_study", "Cross-Sectional Study",
     ["cross sectional study"], "cross_sectional"),
    ("randomized_controlled_trial", "Randomized Controlled Trial",
     ["randomised controlled trial", "rct"],
     "randomized_controlled_trial"),
    ("quasi_experimental_study", "Quasi-Experimental Study",
     ["quasi experimental"], "quasi_experimental"),
    ("experimental_study", "Experimental Study", [], "experimental"),
    ("observational_study", "Observational Study", [], "observational"),
    ("protocol", "Protocol",
     ["study protocol", "trial protocol"], None),
    ("dataset_paper", "Dataset Paper",
     ["data descriptor", "data paper"], "dataset_description"),
    ("software_tool_paper", "Software Tool Paper",
     ["tool paper", "software paper"], "method_development"),
    ("benchmark_paper", "Benchmark Paper", [], "benchmark"),
    ("survey_paper", "Survey Paper", [], "survey"),
    ("position_paper", "Position Paper", [], "theoretical"),
    ("editorial", "Editorial", [], None),
    ("letter", "Letter", ["letter to the editor"], None),
    ("conference_paper", "Conference Paper",
     ["in proceedings of"], None),
    ("thesis", "Thesis",
     ["phd thesis", "doctoral thesis", "master thesis", "dissertation"],
     "theoretical"),
    ("unknown", "Unknown", [], "unknown"),
)


def upgrade() -> None:
    # --- research_designs (paper_types depends on it) --------------------
    op.create_table(
        "research_designs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("aliases", JSONB, nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("taxonomy_version", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_research_designs_active", "research_designs", ["is_active"]
    )

    # --- research_domains ------------------------------------------------
    op.create_table(
        "research_domains",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column(
            "depth", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("aliases", JSONB, nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("taxonomy_version", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "depth >= 0 AND depth <= 3",
            name="ck_research_domains_depth",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["research_domains.id"],
            ondelete="SET NULL",
            name="fk_research_domains_parent_id",
        ),
    )
    op.create_index(
        "ix_research_domains_parent", "research_domains", ["parent_id"]
    )
    op.create_index(
        "ix_research_domains_active", "research_domains", ["is_active"]
    )

    # --- paper_types (FK to research_designs) ----------------------------
    op.create_table(
        "paper_types",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("aliases", JSONB, nullable=True),
        sa.Column("default_design_code", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("taxonomy_version", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["default_design_code"], ["research_designs.code"],
            ondelete="SET NULL",
            name="fk_paper_types_default_design_code",
        ),
    )
    op.create_index("ix_paper_types_active", "paper_types", ["is_active"])

    # --- project_classifications ----------------------------------------
    op.create_table(
        "project_classifications",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("domain_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("domain_source", sa.Text(), nullable=True),
        sa.Column("domain_method", sa.Text(), nullable=True),
        sa.Column("domain_confidence", sa.Float(), nullable=True),
        sa.Column("domain_reason", sa.Text(), nullable=True),
        sa.Column("domain_alternatives", JSONB, nullable=True),
        sa.Column("paper_type_code", sa.Text(), nullable=True),
        sa.Column("paper_type_source", sa.Text(), nullable=True),
        sa.Column("paper_type_method", sa.Text(), nullable=True),
        sa.Column("paper_type_confidence", sa.Float(), nullable=True),
        sa.Column("paper_type_reason", sa.Text(), nullable=True),
        sa.Column("paper_type_alternatives", JSONB, nullable=True),
        sa.Column("paper_type_secondary", JSONB, nullable=True),
        sa.Column("research_design_code", sa.Text(), nullable=True),
        sa.Column("research_design_source", sa.Text(), nullable=True),
        sa.Column("research_design_method", sa.Text(), nullable=True),
        sa.Column(
            "research_design_confidence", sa.Float(), nullable=True
        ),
        sa.Column("research_design_reason", sa.Text(), nullable=True),
        sa.Column("research_design_alternatives", JSONB, nullable=True),
        sa.Column(
            "status", sa.Text(), nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "needs_review", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("classifier_version", sa.Text(), nullable=False),
        sa.Column("taxonomy_version", sa.Text(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed','needs_review','failed')",
            name="ck_project_classifications_status",
        ),
        sa.CheckConstraint(
            "domain_source IS NULL OR "
            "domain_source IN ('explicit','inferred','user_override')",
            name="ck_project_classifications_domain_source",
        ),
        sa.CheckConstraint(
            "domain_method IS NULL OR "
            "domain_method IN ('explicit','heuristic','llm')",
            name="ck_project_classifications_domain_method",
        ),
        sa.CheckConstraint(
            "domain_confidence IS NULL OR "
            "(domain_confidence >= 0.0 AND domain_confidence <= 1.0)",
            name="ck_project_classifications_domain_conf",
        ),
        sa.CheckConstraint(
            "paper_type_source IS NULL OR "
            "paper_type_source IN "
            "('explicit','inferred','user_override')",
            name="ck_project_classifications_paper_source",
        ),
        sa.CheckConstraint(
            "paper_type_method IS NULL OR "
            "paper_type_method IN ('explicit','heuristic','llm')",
            name="ck_project_classifications_paper_method",
        ),
        sa.CheckConstraint(
            "paper_type_confidence IS NULL OR "
            "(paper_type_confidence >= 0.0 "
            "AND paper_type_confidence <= 1.0)",
            name="ck_project_classifications_paper_conf",
        ),
        sa.CheckConstraint(
            "research_design_source IS NULL OR "
            "research_design_source IN "
            "('explicit','inferred','user_override')",
            name="ck_project_classifications_design_source",
        ),
        sa.CheckConstraint(
            "research_design_method IS NULL OR "
            "research_design_method IN ('explicit','heuristic','llm')",
            name="ck_project_classifications_design_method",
        ),
        sa.CheckConstraint(
            "research_design_confidence IS NULL OR "
            "(research_design_confidence >= 0.0 "
            "AND research_design_confidence <= 1.0)",
            name="ck_project_classifications_design_conf",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            ondelete="CASCADE",
            name="fk_project_classifications_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["domain_id"], ["research_domains.id"],
            ondelete="SET NULL",
            name="fk_project_classifications_domain_id_research_domains",
        ),
        sa.ForeignKeyConstraint(
            ["paper_type_code"], ["paper_types.code"],
            ondelete="SET NULL",
            name="fk_project_classifications_paper_type_code",
        ),
        sa.ForeignKeyConstraint(
            ["research_design_code"], ["research_designs.code"],
            ondelete="SET NULL",
            name="fk_project_classifications_design_code",
        ),
        sa.UniqueConstraint(
            "project_id", name="ux_project_classifications_project"
        ),
    )
    op.create_index(
        "ix_project_classifications_status",
        "project_classifications",
        ["status"],
    )
    op.create_index(
        "ix_project_classifications_paper_type",
        "project_classifications",
        ["paper_type_code"],
    )
    op.create_index(
        "ix_project_classifications_design",
        "project_classifications",
        ["research_design_code"],
    )
    op.create_index(
        "ix_project_classifications_context_hash",
        "project_classifications",
        ["project_id", "context_hash"],
    )

    # --- classification_evidence ----------------------------------------
    op.create_table(
        "classification_evidence",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "classification_id", PGUUID(as_uuid=True), nullable=False
        ),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("signal_type", sa.Text(), nullable=False),
        sa.Column("source_location", sa.Text(), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("target_code", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "target IN ('domain','paper_type','research_design')",
            name="ck_classification_evidence_target",
        ),
        sa.CheckConstraint(
            "weight >= 0.0 AND weight <= 1.0",
            name="ck_classification_evidence_weight",
        ),
        sa.ForeignKeyConstraint(
            ["classification_id"], ["project_classifications.id"],
            ondelete="CASCADE",
            name="fk_classification_evidence_classification_id",
        ),
    )
    op.create_index(
        "ix_classification_evidence_class_target",
        "classification_evidence",
        ["classification_id", "target"],
    )

    # --- extend ProjectEvent CHECK ---------------------------------------
    op.drop_constraint(
        "ck_project_events_type", "project_events", type_="check"
    )
    op.create_check_constraint(
        "ck_project_events_type",
        "project_events",
        "event_type IN "
        "('project_created','project_updated','project_archived',"
        "'classification_recomputed','classification_overridden',"
        "'classification_failed')",
    )

    # --- seed ------------------------------------------------------------
    conn = op.get_bind()

    for code, name, aliases in _DESIGNS:
        conn.execute(
            sa.text(
                "INSERT INTO research_designs "
                "(id, code, name, description, aliases, "
                " is_active, taxonomy_version) "
                "VALUES (:id, :code, :name, NULL, "
                "        CAST(:aliases AS jsonb), true, :v)"
            ),
            {
                "id": _ru(code),
                "code": code,
                "name": name,
                "aliases": json.dumps(aliases),
                "v": TAXONOMY_VERSION,
            },
        )

    for code, name, parent_code, depth, aliases in _DOMAINS:
        conn.execute(
            sa.text(
                "INSERT INTO research_domains "
                "(id, code, name, parent_id, depth, description, "
                " aliases, is_active, taxonomy_version) "
                "VALUES (:id, :code, :name, :pid, :depth, NULL, "
                "        CAST(:aliases AS jsonb), true, :v)"
            ),
            {
                "id": _du(code),
                "code": code,
                "name": name,
                "pid": _du(parent_code) if parent_code else None,
                "depth": depth,
                "aliases": json.dumps(aliases),
                "v": TAXONOMY_VERSION,
            },
        )

    for code, name, aliases, default_design in _PAPER_TYPES:
        conn.execute(
            sa.text(
                "INSERT INTO paper_types "
                "(id, code, name, description, aliases, "
                " default_design_code, is_active, taxonomy_version) "
                "VALUES (:id, :code, :name, NULL, "
                "        CAST(:aliases AS jsonb), :dd, true, :v)"
            ),
            {
                "id": _pu(code),
                "code": code,
                "name": name,
                "aliases": json.dumps(aliases),
                "dd": default_design,
                "v": TAXONOMY_VERSION,
            },
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM project_events WHERE event_type IN "
        "('classification_recomputed','classification_overridden',"
        "'classification_failed')"
    )
    op.drop_constraint(
        "ck_project_events_type", "project_events", type_="check"
    )
    op.create_check_constraint(
        "ck_project_events_type",
        "project_events",
        "event_type IN "
        "('project_created','project_updated','project_archived')",
    )

    op.drop_index(
        "ix_classification_evidence_class_target",
        table_name="classification_evidence",
    )
    op.drop_table("classification_evidence")

    op.drop_index(
        "ix_project_classifications_context_hash",
        table_name="project_classifications",
    )
    op.drop_index(
        "ix_project_classifications_design",
        table_name="project_classifications",
    )
    op.drop_index(
        "ix_project_classifications_paper_type",
        table_name="project_classifications",
    )
    op.drop_index(
        "ix_project_classifications_status",
        table_name="project_classifications",
    )
    op.drop_table("project_classifications")

    op.drop_index("ix_paper_types_active", table_name="paper_types")
    op.drop_table("paper_types")

    op.drop_index(
        "ix_research_domains_active", table_name="research_domains"
    )
    op.drop_index(
        "ix_research_domains_parent", table_name="research_domains"
    )
    op.drop_table("research_domains")

    op.drop_index(
        "ix_research_designs_active", table_name="research_designs"
    )
    op.drop_table("research_designs")