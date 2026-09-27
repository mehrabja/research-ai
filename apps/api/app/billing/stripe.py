"""Stripe billing adapter using Stripe's HTTP API."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx

from app.billing.protocol import BillingProvider
from app.core.exceptions import AppError


class StripeNotConfigured(AppError):
    code = "STRIPE_NOT_CONFIGURED"
    status_code = 503
    message = "Stripe billing is not configured."


class StripeProviderError(AppError):
    code = "STRIPE_PROVIDER_ERROR"
    status_code = 502
    message = "Stripe billing provider request failed."


class StripeWebhookInvalid(AppError):
    code = "STRIPE_WEBHOOK_INVALID"
    status_code = 400
    message = "Stripe webhook signature or payload is invalid."


class StripeBillingProvider(BillingProvider):
    provider_name = "stripe"

    def __init__(
        self,
        *,
        secret_key: str,
        webhook_secret: str,
        price_map: dict[str, str],
    ) -> None:
        if not secret_key.strip():
            raise StripeNotConfigured()
        self._secret = secret_key
        self.webhook_secret = webhook_secret.strip()
        self._price_map = price_map

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._secret}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            with httpx.Client(
                base_url="https://api.stripe.com",
                timeout=30.0,
            ) as client:
                response = client.request(
                    method,
                    path,
                    data=data,
                    headers=headers,
                )
                payload = response.json()
        except (OSError, httpx.HTTPError, ValueError) as exc:
            raise StripeProviderError("Stripe request failed") from exc
        if response.status_code >= 400 or not isinstance(payload, dict):
            raise StripeProviderError("Stripe returned an error")
        return payload

    def create_customer(
        self,
        *,
        workspace_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        email: str | None = None,
        name: str | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        data: dict[str, Any] = {
            "metadata[workspace_id]": str(workspace_id),
            "metadata[owner_user_id]": str(owner_user_id),
        }
        if email:
            data["email"] = email
        if name:
            data["name"] = name
        payload = self._request(
            "POST",
            "/v1/customers",
            data=data,
            idempotency_key=idempotency_key,
        )
        customer_id = payload.get("id")
        if not isinstance(customer_id, str):
            raise StripeProviderError("Stripe customer response has no id")
        return customer_id

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
        data: dict[str, Any] = {
            "mode": "subscription",
            "customer": customer_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": client_reference_id,
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
        }
        for key, value in metadata.items():
            data[f"metadata[{key}]"] = value
            data[f"subscription_data[metadata][{key}]"] = value
        return self._request(
            "POST",
            "/v1/checkout/sessions",
            data=data,
            idempotency_key=idempotency_key,
        )

    def create_subscription(
        self,
        *,
        customer_id: str,
        plan_code: str,
        idempotency_key: str | None = None,
    ) -> str:
        price_id = self._price_map.get(plan_code)
        if not price_id:
            raise StripeNotConfigured(
                f"no Stripe price configured for plan {plan_code!r}"
            )
        payload = self._request(
            "POST",
            "/v1/subscriptions",
            data={
                "customer": customer_id,
                "items[0][price]": price_id,
            },
            idempotency_key=idempotency_key,
        )
        subscription_id = payload.get("id")
        if not isinstance(subscription_id, str):
            raise StripeProviderError("Stripe subscription response has no id")
        return subscription_id

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
        self._request(
            "POST",
            f"/v1/subscriptions/{subscription_id}",
            data={"cancel_at_period_end": "false"},
            idempotency_key=idempotency_key,
        )

    def get_subscription(
        self,
        *,
        subscription_id: str,
    ) -> dict[str, Any] | None:
        try:
            return self._request(
                "GET",
                f"/v1/subscriptions/{subscription_id}",
            )
        except StripeProviderError:
            return None

    def list_invoices(
        self,
        *,
        customer_id: str,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/v1/invoices?{urlencode({'customer': customer_id, 'limit': min(limit, 100)})}",
        )
        data = payload.get("data")
        return list(data) if isinstance(data, list) else []

    def construct_webhook_event(
        self,
        *,
        raw_body: bytes,
        signature: str,
        tolerance_seconds: int = 300,
    ) -> dict[str, Any]:
        if not self.webhook_secret:
            raise StripeNotConfigured(
                "Stripe webhook signing secret is not configured"
            )
        try:
            parts = dict(
                item.split("=", 1)
                for item in signature.split(",")
                if "=" in item
            )
            timestamp = int(parts["t"])
            expected = hmac.new(
                self.webhook_secret.encode("utf-8"),
                f"{timestamp}.".encode("utf-8") + raw_body,
                hashlib.sha256,
            ).hexdigest()
            supplied = [
                value
                for key, value in (
                    item.split("=", 1)
                    for item in signature.split(",")
                    if "=" in item
                )
                if key == "v1"
            ]
            if not supplied or not any(
                hmac.compare_digest(expected, value) for value in supplied
            ):
                raise ValueError("signature mismatch")
            if abs(int(time.time()) - timestamp) > tolerance_seconds:
                raise ValueError("signature timestamp outside tolerance")
            event = json.loads(raw_body.decode("utf-8"))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StripeWebhookInvalid() from exc
        if not isinstance(event, dict):
            raise StripeWebhookInvalid()
        return event
