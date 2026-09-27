"""Billing provider resolver."""
from __future__ import annotations

import json

from app.billing.fake import FakeBillingProvider
from app.billing.protocol import BillingProvider
from app.billing.stripe import StripeBillingProvider
from app.core.config import get_settings
from app.core.exceptions import AppError


class BillingProviderUnavailable(AppError):
    code = "BILLING_PROVIDER_UNAVAILABLE"
    status_code = 503
    message = "Billing provider is not configured."


def build_billing_provider() -> BillingProvider:
    settings = get_settings()
    if settings.billing_provider == "fake":
        return FakeBillingProvider()
    if settings.billing_provider == "stripe":
        try:
            price_map = json.loads(settings.stripe_price_map_json or "{}")
        except json.JSONDecodeError as exc:
            raise BillingProviderUnavailable(
                "STRIPE_PRICE_MAP_JSON is invalid."
            ) from exc
        if not isinstance(price_map, dict):
            raise BillingProviderUnavailable(
                "STRIPE_PRICE_MAP_JSON must be an object."
            )
        normalized = {
            str(key): str(value)
            for key, value in price_map.items()
            if str(key).strip() and str(value).strip()
        }
        return StripeBillingProvider(
            secret_key=settings.stripe_secret_key,
            webhook_secret=settings.stripe_webhook_secret,
            price_map=normalized,
        )
    raise BillingProviderUnavailable()
