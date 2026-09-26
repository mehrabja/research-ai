"""Stripe Billing adapter using the HTTP API."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.integrations.billing.base import (
    BillingAuthenticationError,
    BillingInvalidRequestError,
    BillingRateLimitError,
    BillingUnavailableError,
)


class StripeBillingProvider:
    provider_name = "stripe"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.stripe_api_key:
            raise BillingAuthenticationError("Stripe API key is not configured.")
        self._api_key = settings.stripe_api_key
        self._base_url = settings.stripe_api_base_url.rstrip("/")
        self._webhook_secret = settings.stripe_webhook_secret

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            response = httpx.request(
                method,
                self._base_url + path,
                data=data,
                headers=headers,
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise BillingUnavailableError(type(exc).__name__) from exc
        if response.status_code in (401, 403):
            raise BillingAuthenticationError(f"HTTP {response.status_code}")
        if response.status_code == 429:
            raise BillingRateLimitError("HTTP 429")
        if response.status_code >= 500:
            raise BillingUnavailableError(f"HTTP {response.status_code}")
        if response.status_code >= 400:
            raise BillingInvalidRequestError(f"HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise BillingUnavailableError("Stripe returned invalid JSON.") from exc
        if not isinstance(body, dict):
            raise BillingUnavailableError("Stripe response is not an object.")
        return body

    def create_customer(
        self,
        *,
        workspace_id,
        owner_user_id,
        email: str,
        idempotency_key: str | None = None,
    ) -> str:
        body = self._request(
            "POST",
            "/v1/customers",
            data={
                "email": email,
                "metadata[workspace_id]": str(workspace_id),
                "metadata[owner_user_id]": str(owner_user_id),
            },
            idempotency_key=idempotency_key,
        )
        customer_id = body.get("id")
        if not isinstance(customer_id, str):
            raise BillingUnavailableError("Stripe customer response missing id.")
        return customer_id

    def create_checkout_session(
        self,
        *,
        customer_id: str | None,
        customer_email: str,
        price_id: str,
        workspace_id,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        data = {
            "mode": "subscription",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": str(workspace_id),
            "metadata[workspace_id]": str(workspace_id),
            "subscription_data[metadata][workspace_id]": str(workspace_id),
        }
        if customer_id:
            data["customer"] = customer_id
        else:
            data["customer_email"] = customer_email
        return self._request(
            "POST",
            "/v1/checkout/sessions",
            data=data,
            idempotency_key=idempotency_key,
        )

    def get_subscription(self, *, subscription_id: str) -> dict[str, Any] | None:
        return self._request("GET", f"/v1/subscriptions/{subscription_id}")

    def cancel_subscription(
        self,
        *,
        subscription_id: str,
        at_period_end: bool = True,
        idempotency_key: str | None = None,
    ) -> None:
        self._request(
            "POST",
            f"/v1/subscriptions/{subscription_id}",
            data={"cancel_at_period_end": "true" if at_period_end else "false"},
            idempotency_key=idempotency_key,
        )

    def resume_subscription(
        self,
        *,
        subscription_id: str,
        idempotency_key: str | None = None,
    ) -> None:
        self._request(
            "POST",
            f"/v1/subscriptions/{subscription_id}",
            data={"cancel_at_period_end": "false"},
            idempotency_key=idempotency_key,
        )

    def update_subscription_price(
        self,
        *,
        subscription_id: str,
        price_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        current = self.get_subscription(subscription_id=subscription_id)
        items = current.get("items", {}).get("data") if current else None
        if not isinstance(items, list) or not items:
            raise BillingInvalidRequestError("Stripe subscription has no billable item.")
        item_id = items[0].get("id")
        if not isinstance(item_id, str):
            raise BillingInvalidRequestError("Stripe subscription item id missing.")
        return self._request(
            "POST",
            f"/v1/subscriptions/{subscription_id}",
            data={"items[0][id]": item_id, "items[0][price]": price_id},
            idempotency_key=idempotency_key,
        )

    def create_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> str:
        body = self._request(
            "POST",
            "/v1/billing_portal/sessions",
            data={"customer": customer_id, "return_url": return_url},
        )
        url = body.get("url")
        if not isinstance(url, str):
            raise BillingUnavailableError("Stripe portal URL missing.")
        return url

    def list_invoices(
        self,
        *,
        customer_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        body = self._request(
            "GET",
            "/v1/invoices",
            data={"customer": customer_id, "limit": str(max(1, min(limit, 100)))},
        )
        rows = body.get("data")
        return rows if isinstance(rows, list) else []

    def verify_webhook(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> dict[str, Any]:
        if not self._webhook_secret:
            raise BillingAuthenticationError("Stripe webhook secret is not configured.")
        timestamp: str | None = None
        signatures: list[str] = []
        for part in signature.split(","):
            key, _, value = part.partition("=")
            if key == "t":
                timestamp = value
            elif key == "v1":
                signatures.append(value)
        if not timestamp or not signatures:
            raise BillingAuthenticationError("Invalid Stripe signature.")
        try:
            timestamp_int = int(timestamp)
        except ValueError as exc:
            raise BillingAuthenticationError("Invalid Stripe timestamp.") from exc
        if abs(int(time.time()) - timestamp_int) > 300:
            raise BillingAuthenticationError("Stale Stripe webhook.")
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
        expected = hmac.new(
            self._webhook_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        if not any(hmac.compare_digest(expected, item) for item in signatures):
            raise BillingAuthenticationError("Invalid Stripe signature.")
        try:
            body = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise BillingInvalidRequestError("Invalid Stripe webhook JSON.") from exc
        if not isinstance(body, dict) or not isinstance(body.get("id"), str) or not isinstance(body.get("type"), str):
            raise BillingInvalidRequestError("Invalid Stripe event.")
        return body
