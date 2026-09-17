"""Map provider/service exceptions to retryable error codes.

Typed explicit mapping only. No class-name substring inspection.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def classify_exception(exc: BaseException) -> str:
    try:
        from app.integrations.embeddings.base import (
            EmbeddingAuthenticationError,
            EmbeddingInputTooLargeError,
            EmbeddingInvalidRequestError,
            EmbeddingInvalidResponseError,
            EmbeddingProviderUnavailableError,
            EmbeddingRateLimitError,
        )
    except Exception:
        pass
    else:
        if isinstance(exc, EmbeddingRateLimitError):
            return "rate_limited"
        if isinstance(exc, EmbeddingProviderUnavailableError):
            return "provider_unavailable"
        if isinstance(exc, EmbeddingAuthenticationError):
            return "authentication_error"
        if isinstance(exc, EmbeddingInvalidRequestError):
            return "invalid_payload"
        if isinstance(exc, EmbeddingInvalidResponseError):
            return "invalid_provider_response"
        if isinstance(exc, EmbeddingInputTooLargeError):
            return "input_too_large"

    try:
        from app.integrations.generation.base import (
            GenerationAuthenticationError,
            GenerationInputTooLargeError,
            GenerationInvalidRequestError,
            GenerationInvalidResponseError,
            GenerationProviderUnavailableError,
            GenerationRateLimitError,
            GenerationTimeoutError,
        )
    except Exception:
        pass
    else:
        if isinstance(exc, GenerationRateLimitError):
            return "rate_limited"
        if isinstance(exc, GenerationTimeoutError):
            return "provider_timeout"
        if isinstance(exc, GenerationProviderUnavailableError):
            return "provider_unavailable"
        if isinstance(exc, GenerationAuthenticationError):
            return "authentication_error"
        if isinstance(exc, GenerationInvalidRequestError):
            return "invalid_payload"
        if isinstance(exc, GenerationInvalidResponseError):
            return "invalid_provider_response"
        if isinstance(exc, GenerationInputTooLargeError):
            return "input_too_large"

    try:
        from app.integrations.detection.base import (
            DetectionAuthenticationError,
            DetectionInputTooLargeError,
            DetectionInvalidRequestError,
            DetectionInvalidResponseError,
            DetectionProviderUnavailableError,
            DetectionRateLimitError,
            DetectionTimeoutError,
        )
    except Exception:
        pass
    else:
        if isinstance(exc, DetectionRateLimitError):
            return "rate_limited"
        if isinstance(exc, DetectionTimeoutError):
            return "provider_timeout"
        if isinstance(exc, DetectionProviderUnavailableError):
            return "provider_unavailable"
        if isinstance(exc, DetectionAuthenticationError):
            return "authentication_error"
        if isinstance(exc, DetectionInvalidRequestError):
            return "invalid_payload"
        if isinstance(exc, DetectionInvalidResponseError):
            return "invalid_provider_response"
        if isinstance(exc, DetectionInputTooLargeError):
            return "input_too_large"

    try:
        from app.integrations.translation.base import (
            TranslationAuthenticationError,
            TranslationInputTooLargeError,
            TranslationInvalidRequestError,
            TranslationInvalidResponseError,
            TranslationProviderUnavailableError,
            TranslationRateLimitError,
            TranslationTimeoutError,
        )
    except Exception:
        pass
    else:
        if isinstance(exc, TranslationRateLimitError):
            return "rate_limited"
        if isinstance(exc, TranslationTimeoutError):
            return "provider_timeout"
        if isinstance(exc, TranslationProviderUnavailableError):
            return "provider_unavailable"
        if isinstance(exc, TranslationAuthenticationError):
            return "authentication_error"
        if isinstance(exc, TranslationInvalidRequestError):
            return "invalid_payload"
        if isinstance(exc, TranslationInvalidResponseError):
            return "invalid_provider_response"
        if isinstance(exc, TranslationInputTooLargeError):
            return "input_too_large"

    if isinstance(exc, TimeoutError):
        return "provider_timeout"
    if isinstance(exc, ConnectionError):
        return "connection_reset"

    from sqlalchemy.exc import (
        DBAPIError,
        OperationalError,
    )
    from sqlalchemy.exc import (
        TimeoutError as SATimeoutError,
    )
    if isinstance(exc, SATimeoutError):
        return "provider_timeout"
    if isinstance(exc, (OperationalError, DBAPIError)):
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == "40P01":
            return "deadlock"
        if sqlstate == "40001":
            return "serialization_failure"
        return "database_error"

    from app.core.exceptions import (
        DetectionAlreadyCompletedError,
        InvalidJobStateError,
        JobLeaseLostError,
        JobNotFoundError,
        JobPayloadTooLargeError,
        NoEvidenceAvailableError,
        UnknownJobTypeError,
    )
    if isinstance(exc, JobLeaseLostError):
        return "lease_lost"
    if isinstance(exc, UnknownJobTypeError):
        return "unknown_job_type"
    if isinstance(exc, JobPayloadTooLargeError):
        return "input_too_large"
    if isinstance(exc, InvalidJobStateError):
        return "invalid_state"
    if isinstance(exc, JobNotFoundError):
        return "permanent_business_error"
    if isinstance(exc, NoEvidenceAvailableError):
        return "permanent_business_error"
    if isinstance(exc, DetectionAlreadyCompletedError):
        return "detection_already_completed"

    logger.debug("unclassified_exception")
    return "unexpected_error"


__all__ = ["classify_exception"]
