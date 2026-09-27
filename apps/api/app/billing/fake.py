"""M37 — Deterministic, in-memory BillingProvider for tests.

* no network calls
* idempotent via ``idempotency_key``
* stable identifiers (``cust-<hex>``, ``sub-<hex>``)
"""
from __future__ import annotations

import secrets
import uuid
from typing import Any


class FakeBillingProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self._customers: dict[str, dict[str, Any]] = {}
        self._subscriptions: dict[str, dict[str, Any]] = {}
        self._idem: dict[str, str] = {}

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{secrets.token_hex(8)}"

    def create_customer(
        self,
        *,
        workspace_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        email: str | None = None,
        name: str | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        if idempotency_key is not None:
            existing = self._idem.get(idempotency_key)
            if existing is not None:
                return existing
        cid = self._new_id("cust")
        self._customers[cid] = {
            "workspace_id": str(workspace_id),
            "owner_user_id": str(owner_user_id),
        }
        if idempotency_key is not None:
            self._idem[idempotency_key] = cid
        return cid

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
    ) -> dict[str, Any]:
        if idempotency_key is not None and idempotency_key in self._idem:
            sid = self._idem[idempotency_key]
            return {"id": sid, "url": f"{success_url}?checkout={sid}", "status": "open"}
        if customer_id not in self._customers:
            raise ValueError(f"unknown customer: {customer_id}")
        checkout_id = self._new_id("cs_test")
        if idempotency_key is not None:
            self._idem[idempotency_key] = checkout_id
        return {
            "id": checkout_id,
            "url": f"{success_url}?checkout={checkout_id}",
            "status": "open",
            "customer": customer_id,
            "price_id": price_id,
            "cancel_url": cancel_url,
            "client_reference_id": client_reference_id,
            "metadata": dict(metadata),
        }

    def create_subscription(
        self,
        *,
        customer_id: str,
        plan_code: str,
        idempotency_key: str | None = None,
    ) -> str:
        if idempotency_key is not None:
            existing = self._idem.get(idempotency_key)
            if existing is not None:
                return existing
        if customer_id not in self._customers:
            raise ValueError(f"unknown customer: {customer_id}")
        sid = self._new_id("sub")
        self._subscriptions[sid] = {
            "customer_id": customer_id,
            "plan_code": plan_code,
            "cancel_at_period_end": False,
        }
        if idempotency_key is not None:
            self._idem[idempotency_key] = sid
        return sid

    def cancel_subscription(
        self,
        *,
        subscription_id: str,
        at_period_end: bool = True,
        idempotency_key: str | None = None,
    ) -> None:
        sub = self._subscriptions.get(subscription_id)
        if sub is None:
            raise ValueError(
                f"unknown subscription: {subscription_id}"
            )
        sub["cancel_at_period_end"] = bool(at_period_end)

    def resume_subscription(
        self,
        *,
        subscription_id: str,
        idempotency_key: str | None = None,
    ) -> None:
        sub = self._subscriptions.get(subscription_id)
        if sub is None:
            raise ValueError(
                f"unknown subscription: {subscription_id}"
            )
        sub["cancel_at_period_end"] = False

    def get_subscription(
        self, *, subscription_id: str
    ) -> dict[str, Any] | None:
        sub = self._subscriptions.get(subscription_id)
        return dict(sub) if sub is not None else None

    def list_invoices(
        self,
        *,
        customer_id: str,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        if customer_id not in self._customers:
            raise ValueError(f"unknown customer: {customer_id}")
        return []


__all__ = ["FakeBillingProvider"]
