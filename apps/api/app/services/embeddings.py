"""Embedding service.

Owns: claim → provider call → persist → usage.

Invariants
----------
* SKIP LOCKED claiming, short claim transaction.
* Provider HTTP never runs inside a DB transaction.
* Vectors + usage_logs commit in ONE transaction per batch.
* Batch idempotency key includes per-chunk content hash.
* Batch size respects provider item-count and (when tiktoken is
  available) per-request token budget.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    EmbeddingConfigurationError,
    EmbeddingInvalidResponseAppError,
    EmbeddingProviderUnavailableAppError,
    EmbeddingRateLimitAppError,
    SourceNotReadyForEmbedding,
)
from app.db.models.ops import UsageLog
from app.db.models.project import Project
from app.db.models.source import Chunk
from app.domain.embeddings import (
    EmbeddingBatchResult,
    EmbeddingProfile,
    build_embedding_profile_id,
)
from app.integrations.embeddings.base import (
    EmbeddingAuthenticationError,
    EmbeddingInputTooLargeError,
    EmbeddingInvalidRequestError,
    EmbeddingInvalidResponseError,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingProviderUnavailableError,
    EmbeddingRateLimitError,
)
from app.services.ai_metering import execute_metered_provider_call
from app.services.reports import get_report
from app.services.sources import get_source_for_report

logger = logging.getLogger(__name__)

_EMBEDDABLE_STATUSES = frozenset({"full_text", "structured_full_text"})

_STATUS_PENDING = "pending"
_STATUS_PROCESSING = "processing"
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"


@dataclass(frozen=True)
class EmbeddingRunResult:
    source_id: uuid.UUID
    total_chunks: int
    already_current: int
    embedded: int