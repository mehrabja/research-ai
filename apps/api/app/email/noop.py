from __future__ import annotations

import uuid


class NoopEmailProvider:
    provider_name = "none"

    def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        idempotency_key: str | None = None,
    ) -> str:
        return f"noop-{uuid.uuid4()}"
