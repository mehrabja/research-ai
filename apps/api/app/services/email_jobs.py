"""Durable email job enqueue helpers."""
from __future__ import annotations

import uuid

from app.services.jobs import enqueue_job


def enqueue_verification_email(
    db,
    *,
    user_id: uuid.UUID,
    request_key: str | None = None,
):
    key = request_key or f"verification-email:{user_id}:{uuid.uuid4().hex}"
    return enqueue_job(
        db,
        job_type="send_email_verification",
        payload={"user_id": str(user_id)},
        user_id=user_id,
        idempotency_key=key,
        max_attempts=5,
    )


def enqueue_password_reset_email(
    db,
    *,
    user_id: uuid.UUID,
    request_key: str | None = None,
):
    key = request_key or f"password-reset-email:{user_id}:{uuid.uuid4().hex}"
    return enqueue_job(
        db,
        job_type="send_password_reset",
        payload={"user_id": str(user_id)},
        user_id=user_id,
        idempotency_key=key,
        max_attempts=5,
    )
