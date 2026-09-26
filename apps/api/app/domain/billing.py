"""M37 — Billing state (provider-agnostic)."""
from __future__ import annotations

SUB_TRIALING = "trialing"
SUB_ACTIVE = "active"
SUB_PAST_DUE = "past_due"
SUB_CANCELED = "canceled"
SUB_EXPIRED = "expired"

SUBSCRIPTION_STATUSES: tuple[str, ...] = (
    SUB_TRIALING,
    SUB_ACTIVE,
    SUB_PAST_DUE,
    SUB_CANCELED,
    SUB_EXPIRED,
)

# Statuses under which the plan's entitlements are granted.
ACTIVE_SUBSCRIPTION_STATUSES: tuple[str, ...] = (
    SUB_TRIALING,
    SUB_ACTIVE,
    SUB_PAST_DUE,
)

PROVIDER_NONE = "none"
PROVIDER_FAKE = "fake"

PROVIDERS: tuple[str, ...] = (PROVIDER_NONE, PROVIDER_FAKE)

BILLING_EVENT_RECEIVED = "received"
BILLING_EVENT_PROCESSED = "processed"
BILLING_EVENT_FAILED = "failed"
BILLING_EVENT_SKIPPED = "skipped"

BILLING_EVENT_STATUSES: tuple[str, ...] = (
    BILLING_EVENT_RECEIVED,
    BILLING_EVENT_PROCESSED,
    BILLING_EVENT_FAILED,
    BILLING_EVENT_SKIPPED,
)


def is_active_status(status: str) -> bool:
    return status in ACTIVE_SUBSCRIPTION_STATUSES
# --------------------------------------------------------------------------
# State machine (M37 Phase 2-F)
# --------------------------------------------------------------------------

SUBSCRIPTION_TRANSITIONS: dict[str, tuple[str, ...]] = {
    SUB_TRIALING: (
        SUB_ACTIVE, SUB_PAST_DUE, SUB_CANCELED, SUB_EXPIRED,
    ),
    SUB_ACTIVE: (SUB_PAST_DUE, SUB_CANCELED, SUB_EXPIRED),
    SUB_PAST_DUE: (SUB_ACTIVE, SUB_CANCELED, SUB_EXPIRED),
    SUB_CANCELED: (SUB_EXPIRED,),
    SUB_EXPIRED: (),
}


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status == to_status:
        return True
    return to_status in SUBSCRIPTION_TRANSITIONS.get(from_status, ())

__all__ = [
    "ACTIVE_SUBSCRIPTION_STATUSES",
    "BILLING_EVENT_FAILED",
    "BILLING_EVENT_PROCESSED",
    "BILLING_EVENT_RECEIVED",
    "BILLING_EVENT_SKIPPED",
    "BILLING_EVENT_STATUSES",
    "PROVIDERS",
    "PROVIDER_FAKE",
    "PROVIDER_NONE",
    "SUBSCRIPTION_STATUSES",
    "SUB_ACTIVE",
    "SUB_CANCELED",
    "SUB_EXPIRED",
    "SUB_PAST_DUE",
    "SUB_TRIALING",
    "is_active_status",
]
