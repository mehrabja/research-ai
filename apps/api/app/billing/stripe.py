from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.config import get_settings


class StripeBillingProvider:
    provider_name = "stripe"

    def __init__(self) -> None:
        settings = get_settings()
        self._secret = settings.stripe_secret_key
        self._base = settings.stripe_api_base_url.rstrip("/")
        self._timeout = 20.0
        self._price_ids = self._parse_prices(settings.stripe_price_ids)

    @staticmethod
    def _parse_prices(raw: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for entry in raw.split(";"):
            entry = entry.strip()
            if not entry or "=" not in entry:
                continue
            plan, price = entry.split("=", 1)
            if plan.strip() and price.strip():
                result[plan.strip()] = price.strip()
        return result

    def _post(
        self,
        path: str,
        *,
        data: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if not self._secret:
            raise RuntimeError("Stripe secret key is not configured")
        headers = {
            "Authorization": f"Bearer {self._secret}",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = httpx.post(
            f"{self._base}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Stripe HTTP {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Stripe returned invalid JSON")
        return payload

    def create_customer(
        self,
        *,
        workspace_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> str:
        payload = self._post(
            "customers",
            data={
                "metadata[workspace_id]": str(workspace_id),
                "metadata[owner_user_id]": str(owner_user_id),
            },
            idempotency_key=idempotency_key,
        )
        customer_id = payload.get("id")
        if not isinstance(customer_id, str):
            raise RuntimeError("Stripe customer response missing id")
        return customer_id

    def create_subscription(
        self,
        *,
        customer_id: str,
        plan_code: str,
        idempotency_key: str | None = None,
    ) -> str:
        price_id = self._price_ids.get(plan_code)
        if not price_id:
            raise RuntimeError(
                f"No Stripe price configured for plan {plan_code!r}"
            )
        payload = self._post(
            "subscriptions",
            data={
                "customer": customer_id,
                "items[0][price]": price_id,
            },
            idempotency_key=idempotency_key,
        )
        subscription_id = payload.get("id")
        if not isinstance(subscription_id, str):
            raise RuntimeError("Stripe subscription response missing id")
        return subscription_id

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        plan_code: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        price_id = self._price_ids.get(plan_code)
        if not price_id:
            raise RuntimeError(
                f"No Stripe price configured for plan {plan_code!r}"
            )
        return self._post(
            "checkout/sessions",
            data={
                "mode": "subscription",
                "customer": customer_id,
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                "success_url": success_url,
                "cancel_url": cancel_url,
            },
            idempotency_key=idempotency_key,
        )

    def cancel_subscription(
        self,
        *,
        subscription_id: str,
        at_period_end: bool = True,
        idempotency_key: str | None = None,
    ) -> None:
        self._post(
            f"subscriptions/{subscription_id}",
            data={
                "cancel_at_period_end": "true" if at_period_end else "false",
            },
            idempotency_key=idempotency_key,
        )

    def resume_subscription(
        self,
        *,
        subscription_id: str,
        idempotency_key: str | None = None,
    ) -> None:
        self._post(
            f"subscriptions/{subscription_id}",
            data={"cancel_at_period_end": "false"},
            idempotency_key=idempotency_key,
        )

    def get_subscription(
        self, *, subscription_id: str
    ) -> dict[str, Any] | None:
        if not self._secret:
            raise RuntimeError("Stripe secret key is not configured")
        response = httpx.get(
            f"{self._base}/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {self._secret}"},
            timeout=self._timeout,
        )
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise RuntimeError(
                f"Stripe HTTP {response.status_code}"
            )
        payload = response.json()
        return payload if isinstance(payload, dict) else None
