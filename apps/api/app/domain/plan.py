"""M37 — Plans / entitlements (provider-agnostic)."""
from __future__ import annotations

PLAN_FREE = "free"
PLAN_PRO = "pro"
PLAN_TEAM = "team"
PLAN_ENTERPRISE = "enterprise"

PLAN_CODES: tuple[str, ...] = (
    PLAN_FREE,
    PLAN_PRO,
    PLAN_TEAM,
    PLAN_ENTERPRISE,
)

# ``enterprise`` is reserved but intentionally NOT seeded by migration
# 0032. Services MUST NOT assume every value in PLAN_CODES has a row.
RESERVED_UNSEEDED_PLAN_CODES: tuple[str, ...] = (PLAN_ENTERPRISE,)

PLAN_STATUS_ACTIVE = "active"
PLAN_STATUS_ARCHIVED = "archived"
PLAN_STATUSES: tuple[str, ...] = (PLAN_STATUS_ACTIVE, PLAN_STATUS_ARCHIVED)

# ----- Features ------------------------------------------------------------
FEATURE_PROJECTS_MAX = "projects.max"
FEATURE_REPORTS_MONTHLY = "reports.monthly"
FEATURE_MEMBERS_MAX = "members.max"
FEATURE_STORAGE_BYTES = "storage.bytes"
FEATURE_AI_GENERATION_UNITS = "ai_generation_units"
FEATURE_SEARCH_REQUESTS = "search.requests"

FEATURES: tuple[str, ...] = (
    FEATURE_PROJECTS_MAX,
    FEATURE_REPORTS_MONTHLY,
    FEATURE_MEMBERS_MAX,
    FEATURE_STORAGE_BYTES,
    FEATURE_AI_GENERATION_UNITS,
    FEATURE_SEARCH_REQUESTS,
)

MONTHLY_FEATURES: tuple[str, ...] = (
    FEATURE_REPORTS_MONTHLY,
    FEATURE_AI_GENERATION_UNITS,
    FEATURE_SEARCH_REQUESTS,
)

GAUGE_FEATURES: tuple[str, ...] = (
    FEATURE_PROJECTS_MAX,
    FEATURE_MEMBERS_MAX,
    FEATURE_STORAGE_BYTES,
)

UNIT_COUNT = "count"
UNIT_BYTES = "bytes"
UNIT_UNITS = "units"
UNIT_REQUESTS = "requests"

UNIT_FOR_FEATURE: dict[str, str] = {
    FEATURE_PROJECTS_MAX: UNIT_COUNT,
    FEATURE_REPORTS_MONTHLY: UNIT_COUNT,
    FEATURE_MEMBERS_MAX: UNIT_COUNT,
    FEATURE_STORAGE_BYTES: UNIT_BYTES,
    FEATURE_AI_GENERATION_UNITS: UNIT_UNITS,
    FEATURE_SEARCH_REQUESTS: UNIT_REQUESTS,
}


def expected_unit(feature: str) -> str:
    unit = UNIT_FOR_FEATURE.get(feature)
    if unit is None:
        raise KeyError(feature)
    return unit


DEFAULT_PLAN_CODE = PLAN_FREE

# Seed data used by migration 0032. Values are placeholders — no
# provider pricing is encoded here.
DEFAULT_PLAN_SEED: tuple[dict, ...] = (
    {
        "code": PLAN_FREE,
        "name": "Free",
        "description": "Default plan.",
        "entitlements": {
            FEATURE_PROJECTS_MAX: 3,
            FEATURE_REPORTS_MONTHLY: 30,
            FEATURE_MEMBERS_MAX: 1,
            FEATURE_STORAGE_BYTES: 100 * 1024 * 1024,
            FEATURE_AI_GENERATION_UNITS: 1_000,
            FEATURE_SEARCH_REQUESTS: 500,
        },
    },
    {
        "code": PLAN_PRO,
        "name": "Pro",
        "description": "Individual power users.",
        "entitlements": {
            FEATURE_PROJECTS_MAX: 50,
            FEATURE_REPORTS_MONTHLY: 500,
            FEATURE_MEMBERS_MAX: 10,
            FEATURE_STORAGE_BYTES: 10 * 1024 * 1024 * 1024,
            FEATURE_AI_GENERATION_UNITS: 50_000,
            FEATURE_SEARCH_REQUESTS: 20_000,
        },
    },
    {
        "code": PLAN_TEAM,
        "name": "Team",
        "description": "Small teams.",
        "entitlements": {
            FEATURE_PROJECTS_MAX: 500,
            FEATURE_REPORTS_MONTHLY: 5_000,
            FEATURE_MEMBERS_MAX: 100,
            FEATURE_STORAGE_BYTES: 100 * 1024 * 1024 * 1024,
            FEATURE_AI_GENERATION_UNITS: 500_000,
            FEATURE_SEARCH_REQUESTS: 200_000,
        },
    },
)


__all__ = [
    "DEFAULT_PLAN_CODE",
    "DEFAULT_PLAN_SEED",
    "FEATURES",
    "FEATURE_AI_GENERATION_UNITS",
    "FEATURE_MEMBERS_MAX",
    "FEATURE_PROJECTS_MAX",
    "FEATURE_REPORTS_MONTHLY",
    "FEATURE_SEARCH_REQUESTS",
    "FEATURE_STORAGE_BYTES",
    "GAUGE_FEATURES",
    "MONTHLY_FEATURES",
    "PLAN_CODES",
    "PLAN_ENTERPRISE",
    "PLAN_FREE",
    "PLAN_PRO",
    "PLAN_STATUSES",
    "PLAN_STATUS_ACTIVE",
    "PLAN_STATUS_ARCHIVED",
    "PLAN_TEAM",
    "RESERVED_UNSEEDED_PLAN_CODES",
    "UNIT_BYTES",
    "UNIT_COUNT",
    "UNIT_FOR_FEATURE",
    "UNIT_REQUESTS",
    "UNIT_UNITS",
    "expected_unit",
]
