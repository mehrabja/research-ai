from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.email_delivery import EmailDelivery


class EmailDeliveryService:
    """Idempotent transactional email delivery."""

    def __init__(self) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        self._provider_name = settings.email_provider
        if self._provider_name == "resend":
            self._provider = ResendEmailProvider()
        else:
            self._provider = None

    def send(
        self,
        db: Session,
        *,
        user_id: uuid.UUID | None,
        to_email: str,
        template: str,
        subject: str,
        html: str,
        idempotency_key: str,
    ) -> EmailDelivery:
        existing = db.execute(
            select(EmailDelivery).where(
                EmailDelivery.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        row = EmailDelivery(
            user_id=user_id,
            to_email=to_email,
            template=template,
            subject=subject,
            idempotency_key=idempotency_key,
            provider=self._provider_name,
        )
        db.add(row)
        db.flush()

        if self._provider is None:
            row.status = "skipped"
            row.last_error = "email provider is not configured"
            db.flush()
            return row

        row.attempt_count += 1
        try:
            provider_message_id = self._provider.send(
                to=to_email,
                subject=subject,
                html=html,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:  # noqa: BLE001
            row.status = "failed"
            row.last_error = str(exc)[:500]
        else:
            row.status = "sent"
            row.provider_message_id = provider_message_id
            row.sent_at = datetime.now(UTC)
        db.flush()
        return row
