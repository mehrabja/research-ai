"""Provider-neutral billing contract."""
from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BillingProvider(Protocol):
    provider_name: str

    def create_customer(
        self,
        *,
        workspace_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        email: str | None = None,
        name: str | None = None,
        idempotency_key: str | None = None,
    ) -> str: ...

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        client_reference_id: str,
        metadata: dict[str, str],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]: ...

    def create_subscription(
        self,
        *,
        customer_id: str,
        plan_code: str,
        idempotency_key: str | None = None,
    ) -> str: ...

    def cancel_subscription(
        self,
        *,
        subscription_id: str,
        at_period_end: bool = True,
        idempotency_key: str | None = None,
    ) -> None: ...

    def change_subscription_plan(
        self,
        *,
        subscription_id: str,
        price_id: str,
        idempotency_key: str | None = None,
    ) -> None: ...

    def price_id_for_plan(self, *, plan_code: str) -> str | None: ...

    def resume_subscription(
        self,
        *,
        subscription_id: str,
        idempotency_key: str | None = None,
    ) -> None: ...

    def get_subscription(
        self, *, subscription_id: str
    ) -> dict[str, Any] | None: ...

    def list_invoices(
        self,
        *,
        customer_id: str,
        limit: int = 25,
    ) -> list[dict[str, Any]]: ...
