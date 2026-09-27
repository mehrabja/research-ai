from __future__ import annotations

from app.billing.protocol import BillingProvider
from app.core.config import get_settings
from app.providers.registry import (
    ProviderCapability,
    ProviderContext,
    resolve_provider,
)


def get_billing_provider() -> BillingProvider:
    settings = get_settings()
    return resolve_provider(
        capability=ProviderCapability.BILLING,
        preferred=settings.billing_provider,
        context=ProviderContext(),
    )
