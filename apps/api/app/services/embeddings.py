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
from functools import partial

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
    failed: int
    pending: int
    profile_id: str
    usage_input_tokens: int


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_current(chunk: Chunk, profile: EmbeddingProfile) -> bool:
    pid = build_embedding_profile_id(profile)
    return (
        chunk.embedding is not None
        and chunk.embedding_status == _STATUS_COMPLETED
        and chunk.embedding_input_hash == _sha256_hex(chunk.content)
        and chunk.embedding_model_version == pid
        and chunk.embedding_provider == profile.provider
        and chunk.embedding_dimensions == profile.dimensions
    )


def build_embedding_batch_idempotency_key(
    *,
    report_id: uuid.UUID,
    source_id: uuid.UUID,
    provider: str,
    model: str,
    profile_id: str,
    batch: Sequence[Chunk],
) -> str:
    """Deterministic key with per-chunk content hash.

    Each member contributes ``chunk_id:content_hash`` so a retry that
    reuses the same chunk ids with new content produces a different
    key. Sorting by the identity string gives stable output regardless
    of batch iteration order.
    """
    identities = sorted(
        f"{c.id}:{_sha256_hex(c.content)}" for c in batch
    )
    material = "|".join(
        [
            str(report_id),
            str(source_id),
            provider,
            model,
            profile_id,
            *identities,
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Claiming
# ---------------------------------------------------------------------------
def claim_embedding_batch(
    db: Session,
    *,
    source_id: uuid.UUID,
    profile: EmbeddingProfile,
    batch_size: int,
    processing_timeout_seconds: int,
) -> list[Chunk]:
    stale_cutoff = datetime.now(UTC) - timedelta(
        seconds=processing_timeout_seconds
    )
    try:
        stmt = (
            select(Chunk)
            .where(Chunk.source_id == source_id)
            .where(
                (Chunk.embedding_status.is_(None))
                | (Chunk.embedding_status == _STATUS_PENDING)
                | (Chunk.embedding_status == _STATUS_FAILED)
                | (
                    (Chunk.embedding_status == _STATUS_PROCESSING)
                    & (
                        (Chunk.embedding_started_at.is_(None))
                        | (Chunk.embedding_started_at < stale_cutoff)
                    )
                )
            )
            .order_by(Chunk.chunk_index.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        chunks = list(db.execute(stmt).scalars().all())
        chunks = [c for c in chunks if not _chunk_current(c, profile)]

        now = datetime.now(UTC)
        for c in chunks:
            c.embedding_status = _STATUS_PROCESSING
            c.embedding_started_at = now
            c.embedding_completed_at = None
            c.embedding_error = None
        db.commit()
        return chunks
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Token-aware batching (provider limits authoritative)
# ---------------------------------------------------------------------------
def _compute_safe_item_cap(
    provider: EmbeddingProvider, max_items: int
) -> int:
    """Fallback item cap when token counting is not available.

    Uses ``max_input_tokens_per_request`` / ``max_input_tokens_per_item``
    to guarantee that the worst-case request cannot exceed the
    provider's request budget, without inventing token counts.
    """
    if (
        provider.max_input_tokens_per_request is None
        or provider.max_input_tokens_per_item is None
        or provider.max_input_tokens_per_item <= 0
    ):
        return min(max_items, provider.max_batch_size)
    ratio = (
        provider.max_input_tokens_per_request
        // provider.max_input_tokens_per_item
    )
    return max(1, min(max_items, provider.max_batch_size, ratio))


def _build_batches(
    chunks: list[Chunk],
    *,
    provider: EmbeddingProvider,
    max_items: int,
) -> list[list[Chunk]]:
    """Split into batches respecting provider limits.

    The token-aware path is only used when the provider's limits are
    declared AND the provider can actually count tokens for this
    content. A provider that declares limits but returns ``None``
    from ``estimate_input_tokens`` (e.g. unknown model, tiktoken
    unavailable) falls back to the item-count path with a
    conservative ``safe_item_cap``.
    """
    if not chunks:
        return []

    sample_tokens = provider.estimate_input_tokens(chunks[0].content)
    tokenizer_works = (
        provider.max_input_tokens_per_request is not None
        and provider.max_input_tokens_per_item is not None
        and sample_tokens is not None
    )

    if not tokenizer_works:
        hard_max = _compute_safe_item_cap(provider, max_items)
        batches: list[list[Chunk]] = []
        current: list[Chunk] = []
        for c in chunks:
            if len(current) >= hard_max:
                batches.append(current)
                current = []
            current.append(c)
        if current:
            batches.append(current)
        return batches

    hard_max_items = min(max_items, provider.max_batch_size)
    batches = []
    current = []
    current_tokens = 0
    for c in chunks:
        tokens = provider.estimate_input_tokens(c.content)
        if tokens is None:
            if current and len(current) >= hard_max_items:
                batches.append(current)
                current = []
                current_tokens = 0
            current.append(c)
            continue

        if tokens > (provider.max_input_tokens_per_item or 0):
            continue

        if current and (
            len(current) >= hard_max_items
            or (
                provider.max_input_tokens_per_request is not None
                and current_tokens + tokens
                > provider.max_input_tokens_per_request
            )
        ):
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(c)
        current_tokens += tokens

    if current:
        batches.append(current)
    return batches


def _embed_documents_for_batch(
    provider: EmbeddingProvider, batch: Sequence[Chunk]
) -> EmbeddingBatchResult:
    return provider.embed_documents([chunk.content for chunk in batch])

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def embed_source(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    source_id: uuid.UUID,
    provider: EmbeddingProvider,
    profile: EmbeddingProfile,
) -> EmbeddingRunResult:
    report = get_report(db, user_id=user_id, report_id=report_id)
    project = db.get(Project, report.project_id) if report.project_id else None
    if project is not None:
        workspace_id = project.workspace_id
    else:
        from app.services.workspaces import get_default_workspace_for_user
        workspace = get_default_workspace_for_user(db, user_id=user_id)
        if workspace is None:
            raise RuntimeError("embedding source has no workspace context")
        workspace_id = workspace.id

    source = get_source_for_report(
        db, user_id=user_id, report_id=report_id, source_id=source_id
    )
    if source.status not in _EMBEDDABLE_STATUSES:
        raise SourceNotReadyForEmbedding()

    profile_id = build_embedding_profile_id(profile)
    settings = get_settings()

    all_chunks = list(
        db.execute(
            select(Chunk).where(Chunk.source_id == source.id)
        ).scalars().all()
    )
    total = len(all_chunks)
    if total == 0:
        return EmbeddingRunResult(
            source_id=source.id,
            total_chunks=0,
            already_current=0,
            embedded=0,
            failed=0,
            pending=0,
            profile_id=profile_id,
            usage_input_tokens=0,
        )

    already_current = sum(
        1 for c in all_chunks if _chunk_current(c, profile)
    )
    if already_current == total:
        return EmbeddingRunResult(
            source_id=source.id,
            total_chunks=total,
            already_current=already_current,
            embedded=0,
            failed=0,
            pending=0,
            profile_id=profile_id,
            usage_input_tokens=0,
        )

    embedded_count = 0
    failed_count = 0
    usage_input_tokens = 0
    aborted_by_provider: Exception | None = None

    while True:
        claimed = claim_embedding_batch(
            db,
            source_id=source.id,
            profile=profile,
            batch_size=settings.embedding_batch_size,
            processing_timeout_seconds=(
                settings.embedding_processing_timeout_seconds
            ),
        )
        if not claimed:
            break

        batches = _build_batches(
            claimed,
            provider=provider,
            max_items=settings.embedding_batch_size,
        )

        batched_ids = {c.id for b in batches for c in b}
        oversized = [c for c in claimed if c.id not in batched_ids]
        if oversized:
            _mark_failed(db, oversized, "input_too_large")
            failed_count += len(oversized)

        for batch in batches:
            try:
                embed_call: Callable[[], EmbeddingBatchResult] = partial(
                    _embed_documents_for_batch, provider, batch
                )
                def input_units(value: EmbeddingBatchResult) -> int:
                    return value.usage.input_tokens
                result = execute_metered_provider_call(
                    embed_call,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    operation="source.embedding.provider_call",
                    capability="embedding",
                    provider=provider,
                    model=profile.model,
                    project_id=report.project_id,
                    report_id=report_id,
                    input_units=input_units,
                )
            except EmbeddingInputTooLargeError as exc:
                _mark_failed(db, batch, "input_too_large")
                failed_count += len(batch)
                raise EmbeddingConfigurationError() from exc
            except EmbeddingRateLimitError as exc:
                _mark_failed(db, batch, "rate_limited")
                failed_count += len(batch)
                aborted_by_provider = exc
                break
            except EmbeddingProviderUnavailableError as exc:
                _mark_failed(db, batch, "provider_unavailable")
                failed_count += len(batch)
                aborted_by_provider = exc
                break
            except EmbeddingAuthenticationError as exc:
                _mark_failed(db, batch, "auth_error")
                failed_count += len(batch)
                raise EmbeddingConfigurationError() from exc
            except EmbeddingInvalidRequestError as exc:
                _mark_failed(db, batch, "invalid_request")
                failed_count += len(batch)
                raise EmbeddingConfigurationError() from exc
            except EmbeddingInvalidResponseError as exc:
                _mark_failed(db, batch, "invalid_response")
                failed_count += len(batch)
                raise EmbeddingInvalidResponseAppError() from exc
            except EmbeddingProviderError as exc:
                _mark_failed(db, batch, "provider_error")
                failed_count += len(batch)
                aborted_by_provider = exc
                break

            if len(result.vectors) != len(batch):
                _mark_failed(db, batch, "count_mismatch")
                failed_count += len(batch)
                raise EmbeddingInvalidResponseAppError()

            _persist_batch_atomic(
                db,
                user_id=user_id,
                report_id=report_id,
                source_id=source.id,
                batch=batch,
                vectors=result.vectors,
                profile=profile,
                profile_id=profile_id,
                input_tokens=result.usage.input_tokens,
                provider_request_id=result.provider_request_id,
            )
            embedded_count += len(batch)
            usage_input_tokens += result.usage.input_tokens

        if aborted_by_provider is not None:
            break

    final_rows = db.execute(
        select(
            Chunk.embedding_status, Chunk.embedding.is_not(None)
        ).where(Chunk.source_id == source.id)
    ).all()
    pending_now = sum(
        1 for st, _ in final_rows
        if st in (None, _STATUS_PENDING, _STATUS_PROCESSING)
    )
    failed_now = sum(1 for st, _ in final_rows if st == _STATUS_FAILED)

    if aborted_by_provider is not None and embedded_count == 0:
        if isinstance(aborted_by_provider, EmbeddingRateLimitError):
            raise EmbeddingRateLimitAppError() from aborted_by_provider
        raise EmbeddingProviderUnavailableAppError() from (
            aborted_by_provider
        )

    return EmbeddingRunResult(
        source_id=source.id,
        total_chunks=total,
        already_current=already_current,
        embedded=embedded_count,
        failed=failed_now or failed_count,
        pending=pending_now,
        profile_id=profile_id,
        usage_input_tokens=usage_input_tokens,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def _persist_batch_atomic(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    source_id: uuid.UUID,
    batch: list[Chunk],
    vectors: list[list[float]],
    profile: EmbeddingProfile,
    profile_id: str,
    input_tokens: int,
    provider_request_id: str | None,
) -> None:
    now = datetime.now(UTC)
    idempotency_key = build_embedding_batch_idempotency_key(
        report_id=report_id,
        source_id=source_id,
        provider=profile.provider,
        model=profile.model,
        profile_id=profile_id,
        batch=batch,
    )

    try:
        existing = db.execute(
            select(UsageLog.id).where(
                UsageLog.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()

        for chunk, vector in zip(batch, vectors, strict=True):
            chunk.embedding = vector
            chunk.embedding_model_version = profile_id
            chunk.embedding_input_hash = _sha256_hex(chunk.content)
            chunk.embedding_provider = profile.provider
            chunk.embedding_dimensions = profile.dimensions
            chunk.embedding_status = _STATUS_COMPLETED
            chunk.embedding_error = None
            chunk.embedding_completed_at = now

        if existing is None and input_tokens > 0:
            metadata: dict[str, object] = {
                "embedding_profile_id": profile_id,
                "batch_size": len(batch),
            }
            if provider_request_id:
                metadata["provider_request_id"] = provider_request_id
            db.add(
                UsageLog(
                    user_id=user_id,
                    report_id=report_id,
                    phase="embedding",
                    provider=profile.provider,
                    model=profile.model,
                    input_tokens=input_tokens,
                    output_tokens=0,
                    idempotency_key=idempotency_key,
                    log_metadata=metadata,
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise


def _mark_failed(db: Session, chunks: list[Chunk], code: str) -> None:
    try:
        for chunk in chunks:
            chunk.embedding_status = _STATUS_FAILED
            chunk.embedding_error = code
        db.commit()
    except Exception:
        db.rollback()
        raise


__all__ = [
    "EmbeddingRunResult",
    "build_embedding_batch_idempotency_key",
    "claim_embedding_batch",
    "embed_source",
]
