"""M37 — Provider-neutral billing abstraction."""
from app.billing.fake import FakeBillingProvider
from app.billing.protocol import BillingProvider

__all__ = ["BillingProvider", "FakeBillingProvider"]
