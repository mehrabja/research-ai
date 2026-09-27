"""M37 — BillingProvider contract.

The billing contract is provider-neutral. Stripe is implemented on this branch; other billing backends can be added without changing business services.
"""
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
        idempotency_key: str | None = None,
    ) -> str: ...

    def create_subscription(
        self,
        *,
        customer_id: str,
        plan_code: str,
        idempotency_key: str | None = None,
    ) -> str: ...

    def update_subscription_plan(
        self,
        *,
        subscription_id: str,
        plan_code: str,
        idempotency_key: str | None = None,
    ) -> None: ...

    def cancel_subscription(
        self,
        *,
        subscription_id: str,
        at_period_end: bool = True,
        idempotency_key: str | None = None,
    ) -> None: ...

    def resume_subscription(
        self,
        *,
        subscription_id: str,
        idempotency_key: str | None = None,
    ) -> None: ...

    def get_subscription(
        self, *, subscription_id: str
    ) -> dict[str, Any] | None: ...
