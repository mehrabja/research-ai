"""Central, type-safe configuration."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_repo_root() -> Path:
    current = Path(__file__).resolve()

    for parent in current.parents:
        if (parent / ".env.example").exists() or (parent / ".git").exists():
            return parent

    return current.parents[2]


REPO_ROOT: Path = _resolve_repo_root()
DEV_JWT_SECRET: str = "dev-insecure-secret-change-me-before-production"
_MIN_JWT_SECRET_BYTES: int = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Agentic Orchestration (Milestone 35) -------------------------
    orchestration_enabled: bool = True
    orchestration_async_jobs: bool = False
    orchestration_job_max_attempts: int = Field(
        default=3, ge=1, le=10
    )
    orchestration_max_nodes: int = Field(default=50, ge=1, le=500)
    orchestration_max_retries_per_node: int = Field(
        default=3, ge=0, le=10
    )
    orchestration_max_provider_calls: int = Field(
        default=100, ge=1, le=1000
    )
    orchestration_max_wall_clock_seconds: int = Field(
        default=3600, ge=60, le=86400
    )
    orchestration_max_total_tokens: int = Field(
        default=500_000, ge=1000, le=10_000_000
    )
    orchestration_max_evidence_volume: int = Field(
        default=1000, ge=1, le=100_000
    )
    orchestration_max_generated_chars: int = Field(
        default=2_000_000, ge=1000, le=50_000_000
    )
    orchestration_require_approval: bool = True

    app_env: str = "development"
    debug: bool = False
    project_name: str = "research-ai"
    api_prefix: str = "/api/v1"

    # --- M36: Production Foundation ------------------------------------
    log_level: str = ""
    log_format: Literal["text", "json"] = "text"

    cors_allowed_origins: str = ""
    cors_allow_credentials: bool = False
    cors_allowed_methods: str = (
        "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    )
    cors_allowed_headers: str = (
        "Authorization,Content-Type,X-Request-ID,X-API-Key"
    )
    cors_exposed_headers: str = "X-Request-ID"

    trusted_hosts: str = "*"
    trusted_proxies: str = ""
    request_id_header: str = "X-Request-ID"
    request_id_accept_incoming: bool = True

    max_request_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        le=100 * 1024 * 1024,
    )
    # Multipart uploads are enforced by the file service while streaming;
    # they must not be buffered by the generic request-size middleware.
    body_limit_stream_uploads: bool = True
    body_limit_stream_upload_suffix: str = "/files"

    rate_limit_enabled: bool = True
    rate_limit_global_per_minute: int = Field(
        default=600, ge=1, le=1_000_000
    )
    rate_limit_user_per_minute: int = Field(
        default=300, ge=1, le=1_000_000
    )
    rate_limit_auth_per_minute: int = Field(
        default=20, ge=1, le=100_000
    )
    rate_limit_upload_per_minute: int = Field(
        default=30, ge=1, le=100_000
    )
    rate_limit_enqueue_per_minute: int = Field(
        default=120, ge=1, le=1_000_000
    )

    readiness_timeout_seconds: float = Field(
        default=3.0, ge=0.1, le=60.0
    )
    graceful_shutdown_timeout_seconds: float = Field(
        default=30.0, ge=1.0, le=300.0
    )

    metrics_enabled: bool = True
    tracing_enabled: bool = False

    secret_backend: Literal["env"] = "env"
    audit_enabled: bool = True
    # --- M36 Chunk 3: Operational / DB pool ---------------------------
    db_pool_size: int = Field(default=5, ge=1, le=200)
    db_max_overflow: int = Field(default=10, ge=0, le=500)
    db_pool_timeout_seconds: float = Field(
        default=30.0, ge=0.1, le=300.0
    )
    db_pool_recycle_seconds: int = Field(
        default=1800, ge=0, le=86400
    )
    db_connect_timeout_seconds: int = Field(
        default=10, ge=1, le=120
    )
    db_statement_timeout_ms: int = Field(
        default=30_000, ge=0, le=3_600_000
    )
    backup_directory: str = "backups"
    backup_retention_days: int = Field(
        default=14, ge=1, le=3650
    )
    database_url: str = Field(..., repr=False)
    # --- M37: SaaS / Billing -------------------------------------------
    billing_provider: Literal["none", "fake", "stripe"] = "none"

    # --- F20: External provider credentials -------------------------------
    openrouter_api_key: str = Field(default="", repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openalex_api_key: str = Field(default="", repr=False)
    crossref_mailto: str = ""
    resend_api_key: str = Field(default="", repr=False)
    email_provider: Literal["none", "resend"] = "none"
    email_from: str = ""
    email_reply_to: str = ""
    web_app_base_url: str = "http://localhost:3000"
    stripe_secret_key: str = Field(default="", repr=False)
    stripe_webhook_secret: str = Field(default="", repr=False)
    stripe_publishable_key: str = ""
    stripe_price_ids: str = ""
    stripe_success_url: str = ""
    stripe_cancel_url: str = ""
    stripe_api_base_url: str = "https://api.stripe.com/v1"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = Field(default="", repr=False)
    google_oauth_redirect_uri: str = ""
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = Field(default="", repr=False)
    github_oauth_redirect_uri: str = ""
    ai_detection_api_key: str = Field(default="", repr=False)
    sentry_dsn: str = ""
    turnstile_secret_key: str = Field(default="", repr=False)
    turnstile_site_key: str = ""

    # --- M39: Provider routing --------------------------------------------
    # Format: capability=provider1,provider2;capability2=provider1
    # The first provider is selected from the capability-specific setting;
    # these entries are appended as ordered transient-failure fallbacks.
    provider_fallbacks: str = ""
    # --- Advanced Humanization (Milestone 32) -------------------------
    manuscript_humanization_enabled: bool = True
    manuscript_humanization_async_jobs: bool = False
    manuscript_humanization_job_max_attempts: int = Field(
        default=3, ge=1, le=10
    )
    manuscript_humanization_max_iterations: int = Field(
        default=3, ge=1, le=20
    )

    # JWT
    jwt_secret_key: str = Field(default=DEV_JWT_SECRET, repr=False)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1)
    jwt_issuer: str = "research-ai"
    jwt_audience: str = "research-ai-api"
    jwt_type: str = "access+jwt"
    jwt_clock_skew_seconds: int = Field(default=30, ge=0)

    # Login throttling
    login_rate_limit: int = Field(default=5, ge=1)
    login_rate_window_seconds: int = Field(default=300, ge=1)

    # --- F02: persistent authentication ---------------------------------
    auth_require_verified_email: bool = False
    auth_refresh_token_expire_days: int = Field(default=30, ge=1, le=365)
    auth_password_reset_expire_minutes: int = Field(default=30, ge=5, le=1440)
    auth_email_verification_expire_hours: int = Field(default=24, ge=1, le=168)
    auth_max_sessions: int = Field(default=10, ge=1, le=100)
    auth_mfa_issuer: str = "research-ai"
    auth_mfa_required: bool = False

    # --- Document extraction (Milestone 8) --------------------------------
    document_fetch_timeout_seconds: float = Field(
        default=20.0, ge=1.0, le=120.0
    )
    document_max_bytes: int = Field(
        default=500 * 1024 * 1024, ge=1024, le=500 * 1024 * 1024
    )
    document_max_redirects: int = Field(default=5, ge=0, le=10)

    # --- Chunking ---------------------------------------------------------
    chunk_target_words: int = Field(default=1200, ge=10, le=10000)
    chunk_overlap_words: int = Field(default=150, ge=0, le=1000)

    # --- Embedding profile (Milestone 9) ----------------------------------
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, ge=1, le=4096)
    embedding_distance_metric: str = "cosine"
    embedding_profile_version: str = "m9.1"

    # --- Embedding runtime ------------------------------------------------
    embedding_openai_api_key: str = Field(default="", repr=False)
    embedding_openai_base_url: str = "https://api.openai.com/v1"
    embedding_batch_size: int = Field(default=64, ge=1, le=512)
    embedding_timeout_seconds: float = Field(
        default=30.0, ge=1.0, le=300.0
    )
    embedding_max_retries: int = Field(default=3, ge=0, le=10)
    embedding_retry_base_seconds: float = Field(
        default=1.0, ge=0.1, le=30.0
    )
    embedding_retry_max_seconds: float = Field(
        default=10.0, ge=0.1, le=120.0
    )
    embedding_retry_jitter_fraction: float = Field(
        default=0.25, ge=0.0, le=1.0
    )
    embedding_processing_timeout_seconds: int = Field(
        default=120, ge=10, le=3600
    )

    # --- Retrieval --------------------------------------------------------
    embedding_retrieval_candidate_multiplier: int = Field(
        default=4, ge=1, le=20
    )
    embedding_retrieval_top_k_default: int = Field(
        default=8, ge=1, le=100
    )
    embedding_retrieval_top_k_max: int = Field(
        default=50, ge=1, le=200
    )
    embedding_rrf_k: int = Field(default=60, ge=1, le=1000)
    embedding_vector_weight: float = Field(
        default=1.0, ge=0.0, le=10.0
    )
    embedding_lexical_weight: float = Field(
        default=1.0, ge=0.0, le=10.0
    )

    # --- HNSW filtered ANN ------------------------------------------------
    embedding_hnsw_ef_search: int = Field(default=100, ge=1, le=4000)
    embedding_hnsw_iterative_scan: Literal[
        "off", "strict_order", "relaxed_order"
    ] = "strict_order"
    embedding_hnsw_max_scan_tuples: int = Field(
        default=20_000, ge=100, le=1_000_000
    )
    embedding_hnsw_scan_mem_multiplier: float = Field(
        default=1.0, ge=0.1, le=10.0
    )

    # --- Job Queue / Worker (Milestone 10) --------------------------------
    job_default_max_attempts: int = Field(default=3, ge=1, le=20)
    job_retry_base_seconds: float = Field(
        default=1.0, ge=0.1, le=60.0
    )
    job_retry_max_seconds: float = Field(
        default=300.0, ge=1.0, le=3600.0
    )
    job_retry_jitter: float = Field(default=0.25, ge=0.0, le=1.0)
    job_processing_timeout_seconds: int = Field(
        default=300, ge=30, le=86400
    )
    job_heartbeat_interval_seconds: int = Field(
        default=30, ge=5, le=3600
    )
    job_poll_interval_seconds: float = Field(
        default=1.0, ge=0.1, le=60.0
    )
    job_payload_max_bytes: int = Field(
        default=65536, ge=256, le=10 * 1024 * 1024
    )

    # --- Universal File Intelligence (Milestone 19) -----------------------
    # Reuses document_max_bytes (M8) as the upload size cap. Do not
    # introduce a second source of truth for "max bytes".
    #
    # Note: extraction jobs use the global ``job_processing_timeout_seconds``
    # (M10) for lease expiry. There is no per-job-type timeout today.
    file_storage_backend: Literal["local", "s3"] = "local"
    storage_endpoint: str = ""
    storage_access_key_id: str = Field(default="", repr=False)
    storage_secret_access_key: str = Field(default="", repr=False)
    storage_bucket: str = ""
    storage_region: str = "auto"
    storage_path_style: bool = True
    file_storage_local_root: str = "storage/files"
    file_chunk_stream_size: int = Field(
        default=1 * 1024 * 1024, ge=4096, le=16 * 1024 * 1024
    )
    file_max_filename_length: int = Field(default=255, ge=32, le=1024)
    file_extraction_max_attempts: int = Field(default=3, ge=1, le=10)

    # --- Code & Data Intelligence (Milestone 20) --------------------------
    intelligence_analysis_version: str = "m20.1"

    # Code intelligence
    code_max_source_bytes: int = Field(
        default=5 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024
    )
    code_max_symbols: int = Field(default=10_000, ge=100, le=100_000)
    code_max_dependencies: int = Field(
        default=5_000, ge=100, le=50_000
    )

    # Data intelligence
    data_profile_max_rows_scanned: int = Field(
        default=100_000, ge=100, le=2_000_000
    )
    data_profile_sample_rows: int = Field(default=100, ge=1, le=1000)
    data_profile_max_columns: int = Field(
        default=500, ge=1, le=5000
    )
    data_profile_top_values_limit: int = Field(
        default=20, ge=1, le=200
    )
    data_profile_distinct_tracking_cap: int = Field(
        default=10_000, ge=100, le=1_000_000
    )
    data_json_max_bytes: int = Field(
        default=50 * 1024 * 1024, ge=1024, le=500 * 1024 * 1024
    )
    data_json_max_depth: int = Field(default=64, ge=4, le=512)
    data_category_max_distinct: int = Field(
        default=50, ge=2, le=1000
    )
    data_xlsx_max_uncompressed_bytes: int = Field(
        default=100 * 1024 * 1024, ge=1024, le=1024 * 1024 * 1024
    )

    source_discovery_provider: str = "semantic_scholar"
    source_discovery_fallbacks: str = ""

    # --- Research Classification (Milestone 21) --------------------------
    detection_api_base_url: str = ""
    detection_api_model: str = "ai-detector-v1"
    detection_timeout_seconds: float = 20.0
    detection_max_input_chars: int = 100_000

    classification_enabled: bool = True
    classification_use_llm: bool = False
    classification_classifier_version: str = "m21.1"
    classification_taxonomy_version: str = "m21.1"

    classification_max_project_text: int = Field(
        default=4000, ge=100, le=50_000
    )
    classification_max_reports: int = Field(default=10, ge=0, le=100)
    classification_max_files: int = Field(default=20, ge=0, le=500)
    classification_max_file_text: int = Field(
        default=1500, ge=0, le=20_000
    )
    classification_max_evidence_items: int = Field(
        default=50, ge=1, le=500
    )
    classification_max_evidence_chars: int = Field(
        default=400, ge=50, le=4000
    )
    classification_max_alternatives: int = Field(
        default=5, ge=1, le=20
    )
    classification_confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0
    )
    classification_review_margin: float = Field(
        default=0.15, ge=0.0, le=1.0
    )
    classification_max_secondary_paper_types: int = Field(
        default=3, ge=0, le=10
    )
    classification_job_max_attempts: int = Field(
        default=3, ge=1, le=10
    )

    # --- Literature Intelligence (Milestone 23) --------------------------
    literature_enabled: bool = True
    literature_async_jobs: bool = False
    literature_job_max_attempts: int = Field(
        default=3, ge=1, le=10
    )

    # --- Research Planning (Milestone 24) --------------------------------
    research_plan_enabled: bool = True
    research_plan_async_jobs: bool = False
    research_plan_llm_required: bool = False
    research_plan_job_max_attempts: int = Field(default=3, ge=1, le=10)
    research_plan_default_word_target: int = Field(
        default=6000, ge=500, le=100_000
    )
    research_plan_llm_timeout_seconds: float = Field(
        default=30.0, ge=1.0, le=300.0
    )

    # --- Knowledge / Evidence Graph (Milestone 25) ------------------------
    knowledge_graph_enabled: bool = True
    knowledge_graph_async_jobs: bool = False
    knowledge_graph_max_traversal_depth: int = Field(
        default=3, ge=1, le=10
    )
    knowledge_graph_max_nodes: int = Field(
        default=500, ge=1, le=10_000
    )
    knowledge_graph_job_max_attempts: int = Field(
        default=3, ge=1, le=10
    )

    # --- Advanced RAG & Research Memory (Milestone 26) -----------------
    rag_enabled: bool = True
    rag_async_jobs: bool = False
    rag_llm_decomposition_enabled: bool = False
    rag_llm_rerank_enabled: bool = False
    rag_max_candidates: int = Field(default=200, ge=10, le=2000)
    rag_max_results: int = Field(default=20, ge=1, le=200)
    rag_max_graph_depth: int = Field(default=2, ge=1, le=5)
    rag_max_graph_nodes: int = Field(default=50, ge=1, le=500)
    rag_diversity_enabled: bool = True
    rag_mmr_lambda: float = Field(default=0.5, ge=0.0, le=1.0)
    rag_memory_enabled: bool = True
    rag_memory_reuse_top_k: int = Field(default=5, ge=0, le=50)
    rag_memory_min_importance: float = Field(
        default=0.3, ge=0.0, le=1.0
    )
    rag_min_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    rag_job_max_attempts: int = Field(default=3, ge=1, le=10)

    # --- Manuscript Architect (Milestone 27) ------------------------------
    manuscript_enabled: bool = True
    manuscript_async_jobs: bool = False
    manuscript_job_max_attempts: int = Field(default=3, ge=1, le=10)
    manuscript_budget_tolerance: float = Field(default=0.10, ge=0.0, le=0.5)

    # --- Section Research (Milestone 28) --------------------------------
    section_research_enabled: bool = True
    section_research_async_jobs: bool = False
    section_research_job_max_attempts: int = Field(default=3, ge=1, le=10)
    section_research_max_queries: int = Field(default=5, ge=1, le=20)
    section_research_max_candidates: int = Field(
        default=200, ge=10, le=2000
    )
    section_research_max_evidence: int = Field(default=30, ge=1, le=200)
    section_research_max_requirements: int = Field(default=10, ge=1, le=100)
    section_research_max_total_excerpt_chars: int = Field(
        default=12000, ge=100, le=200000
    )
    section_research_excerpt_chars: int = Field(
        default=400, ge=50, le=4000
    )
    section_research_coverage_covered_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0
    )
    section_research_coverage_partial_threshold: float = Field(
        default=0.4, ge=0.0, le=1.0
    )

    # --- Manuscript Prose Generation (Milestone 28.5) ----------------
    manuscript_prose_enabled: bool = True
    manuscript_prose_async_jobs: bool = False
    manuscript_prose_job_max_attempts: int = Field(
        default=3, ge=1, le=10
    )
    manuscript_prose_default_mode: str = "hybrid"
    manuscript_prose_provider: str = "openai"
    manuscript_prose_model: str = "gpt-4o-mini"
    manuscript_prose_temperature: float = Field(
        default=0.2, ge=0.0, le=2.0
    )
    manuscript_prose_max_output_tokens: int = Field(
        default=2000, ge=64, le=32000
    )
    manuscript_prose_timeout_seconds: float = Field(
        default=60.0, ge=5.0, le=600.0
    )
    manuscript_prose_max_retries: int = Field(default=2, ge=0, le=10)
    manuscript_prose_max_sections: int = Field(
        default=30, ge=1, le=200
    )
    manuscript_prose_max_paragraphs_per_section: int = Field(
        default=20, ge=1, le=200
    )
    manuscript_prose_max_sentences_per_paragraph: int = Field(
        default=15, ge=1, le=100
    )
    manuscript_prose_max_manuscript_words: int = Field(
        default=30_000, ge=100, le=500_000
    )
    manuscript_prose_max_evidence_per_section: int = Field(
        default=30, ge=1, le=500
    )
    manuscript_prose_max_technical_facts_per_section: int = Field(
        default=30, ge=1, le=500
    )

    # --- Technical Intelligence (Milestone 29) ----------------------------
    technical_intelligence_enabled: bool = True
    technical_intelligence_async_jobs: bool = False
    technical_intelligence_job_max_attempts: int = Field(
        default=3, ge=1, le=10
    )
    technical_intelligence_max_files: int = Field(
        default=500, ge=1, le=5000
    )
    technical_intelligence_max_facts: int = Field(
        default=5000, ge=10, le=100000
    )
    technical_intelligence_max_results: int = Field(
        default=500, ge=1, le=10000
    )
    technical_intelligence_max_metrics: int = Field(
        default=5000, ge=1, le=50000
    )
    technical_intelligence_max_result_rows: int = Field(
        default=200, ge=1, le=5000
    )

    # --- Citation Engine (Milestone 30) --------------------------------
    citation_enabled: bool = True
    citation_async_jobs: bool = False
    citation_job_max_attempts: int = Field(default=3, ge=1, le=10)
    citation_max_claims: int = Field(default=5000, ge=1, le=100000)
    citation_max_evidence_per_claim: int = Field(
        default=50, ge=1, le=500
    )
    citation_support_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0
    )
    citation_partial_threshold: float = Field(
        default=0.3, ge=0.0, le=1.0
    )

    # --- Academic QA (Milestone 31) -----------------------------------
    academic_qa_enabled: bool = True
    academic_qa_async_jobs: bool = False
    academic_qa_job_max_attempts: int = Field(default=3, ge=1, le=10)
    academic_qa_max_findings: int = Field(default=5000, ge=1, le=100000)
    academic_qa_advisory_llm_enabled: bool = False

    # --- Generation (Milestone 12) ----------------------------------------
    generation_provider: str = "openai"
    generation_model: str = "gpt-4o-mini"
    generation_temperature: float = Field(
        default=0.2, ge=0.0, le=2.0
    )
    generation_max_output_tokens: int = Field(
        default=2000, ge=64, le=32000
    )
    generation_max_context_chunks: int = Field(
        default=8, ge=1, le=50
    )
    generation_profile_version: str = "m12.1"
    generation_openai_api_key: str = Field(default="", repr=False)
    generation_openai_base_url: str = "https://api.openai.com/v1"
    generation_timeout_seconds: float = Field(
        default=60.0, ge=5.0, le=600.0
    )
    generation_max_retries: int = Field(default=2, ge=0, le=10)
    generation_retry_base_seconds: float = Field(
        default=1.0, ge=0.1, le=60.0
    )
    generation_retry_max_seconds: float = Field(
        default=30.0, ge=1.0, le=600.0
    )
    generation_retry_jitter_fraction: float = Field(
        default=0.25, ge=0.0, le=1.0
    )

    # --- Publication Targets (Milestone 33) ---------------------------
    publication_targets_enabled: bool = True
    publication_compliance_async_jobs: bool = False
    publication_compliance_job_max_attempts: int = Field(
        default=3, ge=1, le=10
    )
    publication_compliance_max_findings: int = Field(
        default=5000, ge=1, le=100000
    )
    publication_target_max_checklist_items: int = Field(
        default=200, ge=1, le=2000
    )

    # --- Collaboration (Milestone 34) --------------------------------
    collaboration_enabled: bool = True
    collaboration_max_members_per_project: int = Field(
        default=50, ge=2, le=500
    )
    collaboration_max_comments_per_version: int = Field(
        default=1000, ge=1, le=100000
    )
    collaboration_max_review_tasks_per_version: int = Field(
        default=500, ge=1, le=10000
    )
    collaboration_optimistic_lock_enabled: bool = True

    # --- Detection (Milestone 13) -----------------------------------------
    detection_provider: str = "heuristic"
    detection_model: str = "baseline-v1"
    detection_profile_version: str = "m13.1"
    detection_minimum_text_chars: int = Field(
        default=200, ge=0, le=10000
    )

    # --- Humanization (Milestone 14) --------------------------------------
    humanization_enabled: bool = True
    humanization_policy_version: str = "m14.1"
    humanization_temperature: float = Field(
        default=0.4, ge=0.0, le=2.0
    )
    humanization_max_output_tokens: int = Field(
        default=2048, ge=64, le=32000
    )
    humanization_max_segments: int = Field(
        default=50, ge=1, le=500
    )
    humanization_max_total_tokens: int = Field(
        default=60_000, ge=100, le=1_000_000
    )
    humanization_max_segment_chars: int = Field(
        default=4_000, ge=50, le=100_000
    )
    humanization_allow_partial: bool = False
    humanization_max_preservation_retries: int = Field(
        default=1, ge=0, le=5
    )

    # --- Translation (Milestone 16) ---------------------------------------
    translation_enabled: bool = True
    translation_provider: str = "openai"
    translation_model: str = "gpt-4o-mini"
    translation_temperature: float = Field(
        default=0.1, ge=0.0, le=2.0
    )
    translation_max_output_tokens: int = Field(
        default=8000, ge=64, le=16000
    )
    translation_profile_version: str = "m16.1"
    translation_timeout_seconds: float = Field(
        default=90.0, ge=5.0, le=600.0
    )
    translation_max_retries: int = Field(default=2, ge=0, le=10)
    translation_retry_base_seconds: float = Field(
        default=1.0, ge=0.1, le=60.0
    )
    translation_retry_max_seconds: float = Field(
        default=30.0, ge=1.0, le=600.0
    )
    translation_retry_jitter_fraction: float = Field(
        default=0.25, ge=0.0, le=1.0
    )
    translation_max_input_chars: int = Field(
        default=12_000, ge=100, le=1_000_000
    )
    translation_max_output_chars: int = Field(
        default=40_000, ge=100, le=2_000_000
    )
    translation_preservation_retry_count: int = Field(
        default=1, ge=0, le=3
    )

    # --- Post-Translation Humanization (Milestone 17) ---------------------
    post_translation_humanization_enabled: bool = True
    post_translation_humanization_policy_version: str = "m17.1"
    post_translation_humanization_temperature: float = Field(
        default=0.4, ge=0.0, le=2.0
    )
    post_translation_humanization_max_output_tokens: int = Field(
        default=2048, ge=64, le=32000
    )
    post_translation_humanization_max_segments: int = Field(
        default=50, ge=1, le=500
    )
    post_translation_humanization_max_total_tokens: int = Field(
        default=60_000, ge=100, le=1_000_000
    )
    post_translation_humanization_max_segment_chars: int = Field(
        default=4_000, ge=50, le=100_000
    )
    post_translation_humanization_max_preservation_retries: int = Field(
        default=1, ge=0, le=5
    )
    # Lease expiry is DERIVED from provider execution limits. These are
    # added on top of the derived maximum active provider window:
    #   max_active = timeout x (retries + 1)
    #              + retry_max_seconds x (retries + 1)
    #   lease_expires_at = now() + max_active + safety_margin_seconds
    post_translation_humanization_lease_safety_margin_seconds: int = Field(
        default=120, ge=30, le=3600
    )
    post_translation_detection_lease_safety_margin_seconds: int = Field(
        default=60, ge=30, le=3600
    )

    # --- Semantic Scholar / Source Discovery (M7) -------------------------
    semantic_scholar_api_key: str = Field(default="", repr=False)
    semantic_scholar_base_url: str = (
        "https://api.semanticscholar.org/graph/v1"
    )
    semantic_scholar_timeout_seconds: float = Field(
        default=15.0, ge=1.0, le=120.0
    )
    semantic_scholar_max_retries: int = Field(default=3, ge=0, le=10)
    source_search_limit_default: int = Field(default=10, ge=1, le=100)
    source_search_limit_max: int = Field(default=50, ge=1, le=100)

    # ==================================================================
    # M36 helper properties
    # ==================================================================

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            x.strip()
            for x in self.cors_allowed_origins.split(",")
            if x.strip()
        ]

    @property
    def cors_allowed_methods_list(self) -> list[str]:
        return [
            x.strip()
            for x in self.cors_allowed_methods.split(",")
            if x.strip()
        ]

    @property
    def cors_allowed_headers_list(self) -> list[str]:
        return [
            x.strip()
            for x in self.cors_allowed_headers.split(",")
            if x.strip()
        ]

    @property
    def cors_exposed_headers_list(self) -> list[str]:
        return [
            x.strip()
            for x in self.cors_exposed_headers.split(",")
            if x.strip()
        ]

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [
            x.strip()
            for x in self.trusted_hosts.split(",")
            if x.strip()
        ]

    # ==================================================================
    # Validators
    # ==================================================================

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> Settings:
        if self.app_env.lower() == "production":
            if self.jwt_secret_key == DEV_JWT_SECRET:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a non-default value "
                    "when APP_ENV=production."
                )
            if (
                len(self.jwt_secret_key.encode("utf-8"))
                < _MIN_JWT_SECRET_BYTES
            ):
                raise ValueError(
                    f"JWT_SECRET_KEY must be at least "
                    f"{_MIN_JWT_SECRET_BYTES} bytes when "
                    "APP_ENV=production."
                )
        return self

    @model_validator(mode="after")
    def _validate_chunk_config(self) -> Settings:
        if self.chunk_overlap_words >= self.chunk_target_words:
            raise ValueError(
                "chunk_overlap_words must be strictly less than "
                "chunk_target_words"
            )
        return self

    @model_validator(mode="after")
    def _validate_embedding_config(self) -> Settings:
        if self.embedding_distance_metric != "cosine":
            raise ValueError("only cosine is supported")
        if (
            self.embedding_vector_weight
            + self.embedding_lexical_weight
            <= 0
        ):
            raise ValueError("sum of weights must be > 0")
        if (
            self.embedding_retrieval_top_k_max
            < self.embedding_retrieval_top_k_default
        ):
            raise ValueError(
                "top_k_max must be >= top_k_default"
            )
        if (
            self.embedding_retry_max_seconds
            < self.embedding_retry_base_seconds
        ):
            raise ValueError(
                "retry_max must be >= retry_base"
            )
        if self.embedding_hnsw_iterative_scan not in (
            "off", "strict_order", "relaxed_order"
        ):
            raise ValueError(
                "hnsw_iterative_scan must be "
                "off/strict_order/relaxed_order"
            )
        return self

    @model_validator(mode="after")
    def _validate_job_config(self) -> Settings:
        if self.job_retry_max_seconds < self.job_retry_base_seconds:
            raise ValueError(
                "job_retry_max_seconds must be >= "
                "job_retry_base_seconds"
            )
        if (
            self.job_heartbeat_interval_seconds
            >= self.job_processing_timeout_seconds
        ):
            raise ValueError(
                "job_heartbeat_interval_seconds must be < "
                "job_processing_timeout_seconds"
            )
        return self

    @model_validator(mode="after")
    def _validate_generation_config(self) -> Settings:
        if (
            self.generation_retry_max_seconds
            < self.generation_retry_base_seconds
        ):
            raise ValueError(
                "generation_retry_max_seconds must be >= base"
            )
        return self

    @model_validator(mode="after")
    def _validate_detection_config(self) -> Settings:
        if self.detection_minimum_text_chars < 0:
            raise ValueError(
                "detection_minimum_text_chars must be >= 0"
            )
        return self

    @model_validator(mode="after")
    def _validate_source_discovery_config(self) -> Settings:
        if self.source_search_limit_max < self.source_search_limit_default:
            raise ValueError(
                "source_search_limit_max must be >= "
                "source_search_limit_default"
            )
        if not self.semantic_scholar_base_url.startswith(
            ("http://", "https://")
        ):
            raise ValueError(
                "semantic_scholar_base_url must start with http(s)://"
            )
        return self

    @model_validator(mode="after")
    def _validate_file_config(self) -> Settings:
        if self.file_storage_backend not in ("local",):
            raise ValueError("file_storage_backend must be 'local'")
        if not self.file_storage_local_root.strip():
            raise ValueError("file_storage_local_root must not be empty")
        if self.file_chunk_stream_size > self.document_max_bytes:
            raise ValueError(
                "file_chunk_stream_size must be <= document_max_bytes"
            )
        return self

    @model_validator(mode="after")
    def _validate_intelligence_config(self) -> Settings:
        if self.code_max_source_bytes > self.document_max_bytes:
            raise ValueError(
                "code_max_source_bytes must be <= document_max_bytes"
            )
        if self.data_profile_sample_rows > self.data_profile_max_rows_scanned:
            raise ValueError(
                "data_profile_sample_rows must be <= "
                "data_profile_max_rows_scanned"
            )
        if (
            self.data_profile_top_values_limit
            > self.data_profile_distinct_tracking_cap
        ):
            raise ValueError(
                "data_profile_top_values_limit must be <= "
                "data_profile_distinct_tracking_cap"
            )
        if (
            self.data_xlsx_max_uncompressed_bytes
            < self.document_max_bytes
        ):
            raise ValueError(
                "data_xlsx_max_uncompressed_bytes must be >= "
                "document_max_bytes"
            )
        if not self.intelligence_analysis_version.strip():
            raise ValueError(
                "intelligence_analysis_version must not be empty"
            )
        return self

    @model_validator(mode="after")
    def _validate_classification_config(self) -> Settings:
        if self.classification_use_llm:
            raise ValueError(
                "classification_use_llm is reserved for M21.5 and "
                "must remain False in M21"
            )
        if self.classification_max_file_text > (
            self.classification_max_project_text
        ):
            raise ValueError(
                "classification_max_file_text must be <= "
                "classification_max_project_text"
            )
        if self.classification_review_margin > (
            self.classification_confidence_threshold
        ):
            raise ValueError(
                "classification_review_margin must be <= "
                "classification_confidence_threshold"
            )
        return self

    @model_validator(mode="after")
    def _validate_m36_security(self) -> Settings:
        """Fail-closed guards that only apply to production."""
        if self.app_env.lower() == "production":
            if self.debug:
                raise ValueError(
                    "debug must be False when APP_ENV=production."
                )
            if any(
                origin == "*"
                for origin in self.cors_origins_list
            ):
                raise ValueError(
                    "Wildcard CORS origin is not allowed "
                    "when APP_ENV=production."
                )
        if self.db_max_overflow < 0:
            raise ValueError("db_max_overflow must be >= 0")
        if self.db_pool_size < 1:
            raise ValueError("db_pool_size must be >= 1")
        if not self.backup_directory.strip():
            raise ValueError("backup_directory must not be empty")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
