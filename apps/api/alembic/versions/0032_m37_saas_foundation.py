"""M37 — SaaS backend foundation.

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-26

Additive and reversible. Order of operations (must not change):

  1. Create 8 new M37 tables.
  2. Seed plans (free/pro/team) + their entitlements.
     Idempotent via ON CONFLICT.
  3. ADD projects.workspace_id as NULLABLE.
  4. Provision a personal workspace + active owner membership +
     live free subscription for every existing user.
  5. Backfill projects.workspace_id from each project's owner
     membership.
  6. Verify M37 invariants; fail hard if any is violated.
  7. ALTER projects.workspace_id to NOT NULL, add FK + indexes.

Downgrade implications:
  * Drops projects.workspace_id and all 8 M37 tables.
  * Destroys M37-provided workspaces / memberships / subscriptions.
  * Original users and projects rows are preserved.
  * Re-upgrading rebuilds logically-equivalent state (workspace
    UUIDs and slugs may differ).
"""
from __future__ import annotations

import re
import uuid as _uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


# ----- enums mirrored from app.domain.* (kept local on purpose) ------------
WORKSPACE_STATUSES = ("active", "suspended", "deleted")
MEMBERSHIP_ROLES = ("owner", "admin", "member", "viewer")
MEMBERSHIP_STATUSES = ("active", "removed")
PLAN_STATUSES = ("active", "archived")
SUBSCRIPTION_STATUSES = (
    "trialing", "active", "past_due", "canceled", "expired",
)
LIVE_SUBSCRIPTION_STATUSES = ("trialing", "active", "past_due")
PROVIDERS = ("none", "fake")
BILLING_EVENT_STATUSES = ("received", "processed", "failed", "skipped")
USAGE_METRICS = (
    "reports_created", "jobs_enqueued", "files_uploaded",
    "storage_bytes", "ai_generation_units", "search_requests",
)
USAGE_SOURCE_TYPES = (
    "report", "job", "file", "provider_call", "manual", "system",
)
FEATURES = (
    "projects.max", "reports.monthly", "members.max",
    "storage.bytes", "ai_generation_units", "search.requests",
)

PLAN_SEED = (
    {
        "code": "free", "name": "Free",
        "description": "Default plan.",
        "entitlements": {
            "projects.max": 3,
            "reports.monthly": 30,
            "members.max": 1,
            "storage.bytes": 100 * 1024 * 1024,
            "ai_generation_units": 1_000,
            "search.requests": 500,
        },
    },
    {
        "code": "pro", "name": "Pro",
        "description": "Individual power users.",
        "entitlements": {
            "projects.max": 50,
            "reports.monthly": 500,
            "members.max": 10,
            "storage.bytes": 10 * 1024 * 1024 * 1024,
            "ai_generation_units": 50_000,
            "search.requests": 20_000,
        },
    },
    {
        "code": "team", "name": "Team",
        "description": "Small teams.",
        "entitlements": {
            "projects.max": 500,
            "reports.monthly": 5_000,
            "members.max": 100,
            "storage.bytes": 100 * 1024 * 1024 * 1024,
            "ai_generation_units": 500_000,
            "search.requests": 200_000,
        },
    },
)

UNIT_FOR_FEATURE = {
    "projects.max": "count",
    "reports.monthly": "count",
    "members.max": "count",
    "storage.bytes": "bytes",
    "ai_generation_units": "units",
    "search.requests": "requests",
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MIN = 3
_SLUG_MAX = 64
_SLUG_FALLBACK = "ws"


def _in_check(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")"


def _slugify(name: str) -> str:
    """Mirrors app.domain.workspace.slugify; kept local so this
    migration is independent of future domain refactors."""
    s = _SLUG_RE.sub("-", (name or "").strip().lower()).strip("-")
    if not s:
        s = _SLUG_FALLBACK
    if len(s) < _SLUG_MIN:
        s = f"{s}-{_uuid.uuid4().hex[:8]}".strip("-")
    return s[:_SLUG_MAX]


def _unique_slug(conn, base: str) -> str:
    base = _slugify(base)
    candidate = base
    for _ in range(64):
        exists = conn.execute(
            sa.text("SELECT 1 FROM workspaces WHERE slug = :s LIMIT 1"),
            {"s": candidate},
        ).scalar()
        if exists is None:
            return candidate
        candidate = f"{base[:48]}-{_uuid.uuid4().hex[:6]}"
    raise RuntimeError(
        f"migration 0032: could not allocate unique slug from {base!r}"
    )


# ==========================================================================
# upgrade
# ==========================================================================

def upgrade() -> None:
    # ---- 1. Create new tables -------------------------------------------
    _create_workspaces_table()
    _create_memberships_table()
    _create_invitations_table()
    _create_plans_tables()
    _create_subscriptions_table()
    _create_usage_events_table()
    _create_billing_events_table()

    conn = op.get_bind()

    # ---- 2. Seed plans + entitlements (idempotent) ----------------------
    plan_ids = _seed_plans(conn)

    # ---- 3. Add projects.workspace_id NULLABLE --------------------------
    op.add_column(
        "projects",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # ---- 4. Provision personal workspace per existing user --------------
    _provision_workspaces_for_existing_users(conn, plan_ids)

    # ---- 5. Backfill projects.workspace_id ------------------------------
    _backfill_projects(conn)

    # ---- 6. Verify invariants -------------------------------------------
    _verify_invariants(conn)

    # ---- 7. Finalize projects.workspace_id ------------------------------
    op.alter_column(
        "projects", "workspace_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_projects_workspace",
        "projects", "workspaces",
        ["workspace_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_projects_workspace", "projects", ["workspace_id"],
    )
    op.create_index(
        "ix_projects_workspace_status",
        "projects", ["workspace_id", "status"],
    )


# --- table creators --------------------------------------------------------

def _create_workspaces_table() -> None:
    op.create_table(
        "workspaces",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "owner_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'active'"), nullable=False,
        ),
        sa.Column("settings", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("status", WORKSPACE_STATUSES),
            name="ck_workspaces_status",
        ),
        sa.CheckConstraint(
            "char_length(slug) >= 3 AND char_length(slug) <= 64",
            name="ck_workspaces_slug_length",
        ),
    )
    op.create_index("ux_workspaces_slug", "workspaces", ["slug"], unique=True)
    op.create_index("ix_workspaces_owner", "workspaces", ["owner_user_id"])
    op.create_index("ix_workspaces_status", "workspaces", ["status"])


def _create_memberships_table() -> None:
    op.create_table(
        "workspace_memberships",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'active'"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("role", MEMBERSHIP_ROLES),
            name="ck_workspace_memberships_role",
        ),
        sa.CheckConstraint(
            _in_check("status", MEMBERSHIP_STATUSES),
            name="ck_workspace_memberships_status",
        ),
        sa.UniqueConstraint(
            "workspace_id", "user_id",
            name="ux_workspace_memberships_ws_user",
        ),
    )
    op.create_index(
        "ix_workspace_memberships_ws",
        "workspace_memberships", ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_memberships_user",
        "workspace_memberships", ["user_id"],
    )
    op.create_index(
        "ux_workspace_memberships_owner_active",
        "workspace_memberships", ["workspace_id"],
        unique=True,
        postgresql_where=sa.text(
            "role = 'owner' AND status = 'active'"
        ),
    )


def _create_invitations_table() -> None:
    op.create_table(
        "workspace_invitations",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "accepted_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "revoked_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "invited_by_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("role", MEMBERSHIP_ROLES),
            name="ck_workspace_invitations_role",
        ),
        sa.CheckConstraint(
            "char_length(email) > 0",
            name="ck_workspace_invitations_email",
        ),
        sa.CheckConstraint(
            "char_length(token_hash) = 64",
            name="ck_workspace_invitations_token_hash_len",
        ),
    )
    op.create_index(
        "ux_workspace_invitations_token_hash",
        "workspace_invitations", ["token_hash"], unique=True,
    )
    op.create_index(
        "ix_workspace_invitations_ws_status",
        "workspace_invitations",
        ["workspace_id", "accepted_at", "revoked_at"],
    )
    op.create_index(
        "ix_workspace_invitations_email",
        "workspace_invitations", [sa.text("lower(email)")],
    )


def _create_plans_tables() -> None:
    op.create_table(
        "plans",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'active'"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("status", PLAN_STATUSES),
            name="ck_plans_status",
        ),
    )
    op.create_index("ux_plans_code", "plans", ["code"], unique=True)

    op.create_table(
        "plan_entitlements",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "plan_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("limit_value", sa.BigInteger(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("feature", FEATURES),
            name="ck_plan_entitlements_feature",
        ),
        sa.CheckConstraint(
            "limit_value IS NULL OR limit_value >= 0",
            name="ck_plan_entitlements_limit_nonneg",
        ),
        sa.CheckConstraint(
            "unit = CASE feature "
            "  WHEN 'storage.bytes'       THEN 'bytes' "
            "  WHEN 'ai_generation_units' THEN 'units' "
            "  WHEN 'search.requests'     THEN 'requests' "
            "  ELSE 'count' "
            "END",
            name="ck_plan_entitlements_unit",
        ),
        sa.UniqueConstraint(
            "plan_id", "feature",
            name="ux_plan_entitlements_plan_feature",
        ),
    )
    op.create_index(
        "ix_plan_entitlements_plan",
        "plan_entitlements", ["plan_id"],
    )


def _create_subscriptions_table() -> None:
    op.create_table(
        "subscriptions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'active'"), nullable=False,
        ),
        sa.Column(
            "current_period_start", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "current_period_end", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "provider", sa.Text(),
            server_default=sa.text("'none'"), nullable=False,
        ),
        sa.Column("provider_customer_id", sa.Text(), nullable=True),
        sa.Column("provider_subscription_id", sa.Text(), nullable=True),
        sa.Column(
            "cancel_at_period_end", sa.Boolean(),
            server_default=sa.text("false"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("status", SUBSCRIPTION_STATUSES),
            name="ck_subscriptions_status",
        ),
        sa.CheckConstraint(
            _in_check("provider", PROVIDERS),
            name="ck_subscriptions_provider",
        ),
        sa.CheckConstraint(
            "current_period_end IS NULL "
            "OR current_period_start IS NULL "
            "OR current_period_end > current_period_start",
            name="ck_subscriptions_period_order",
        ),
    )
    op.create_index(
        "ux_subscriptions_active_workspace",
        "subscriptions", ["workspace_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('trialing','active','past_due')"
        ),
    )
    op.create_index(
        "ix_subscriptions_workspace",
        "subscriptions", ["workspace_id"],
    )
    op.create_index(
        "ix_subscriptions_provider_customer",
        "subscriptions", ["provider", "provider_customer_id"],
    )


def _create_usage_events_table() -> None:
    op.create_table(
        "usage_events",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=True),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True), nullable=True,
        ),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("metric", USAGE_METRICS),
            name="ck_usage_events_metric",
        ),
        sa.CheckConstraint(
            "source_type IS NULL OR "
            + _in_check("source_type", USAGE_SOURCE_TYPES),
            name="ck_usage_events_source_type",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_usage_events_quantity_pos",
        ),
    )
    op.create_index(
        "ux_usage_events_idempotency",
        "usage_events",
        ["workspace_id", "metric", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "ix_usage_events_ws_metric_occurred",
        "usage_events",
        ["workspace_id", "metric", "occurred_at"],
    )
    op.create_index(
        "ix_usage_events_ws_occurred",
        "usage_events", ["workspace_id", "occurred_at"],
    )
    op.create_index(
        "ix_usage_events_user", "usage_events", ["user_id"],
    )


def _create_billing_events_table() -> None:
    op.create_table(
        "billing_events",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "status", sa.Text(),
            server_default=sa.text("'received'"), nullable=False,
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            _in_check("provider", PROVIDERS),
            name="ck_billing_events_provider",
        ),
        sa.CheckConstraint(
            _in_check("status", BILLING_EVENT_STATUSES),
            name="ck_billing_events_status",
        ),
        sa.CheckConstraint(
            "char_length(payload_hash) = 64",
            name="ck_billing_events_payload_hash_len",
        ),
        sa.UniqueConstraint(
            "provider", "provider_event_id",
            name="ux_billing_events_provider_event",
        ),
    )
    op.create_index(
        "ix_billing_events_status",
        "billing_events", ["status", "received_at"],
    )


# --- seed / backfill / verification ---------------------------------------

def _seed_plans(conn) -> dict[str, object]:
    """Idempotent seed. Returns {code: plan_id (UUID)}."""
    plan_ids: dict[str, object] = {}
    for entry in PLAN_SEED:
        pid = conn.execute(
            sa.text(
                "INSERT INTO plans (code, name, description, status) "
                "VALUES (:c, :n, :d, 'active') "
                "ON CONFLICT (code) DO UPDATE "
                "  SET name = EXCLUDED.name, "
                "      description = EXCLUDED.description "
                "RETURNING id"
            ),
            {
                "c": entry["code"],
                "n": entry["name"],
                "d": entry["description"],
            },
        ).scalar()
        if pid is None:
            raise RuntimeError(
                f"migration 0032: could not upsert plan {entry['code']!r}"
            )
        plan_ids[entry["code"]] = pid

        for feature, limit in entry["entitlements"].items():
            unit = UNIT_FOR_FEATURE[feature]
            conn.execute(
                sa.text(
                    "INSERT INTO plan_entitlements "
                    "(plan_id, feature, limit_value, unit) "
                    "VALUES (:p, :f, :l, :u) "
                    "ON CONFLICT (plan_id, feature) DO UPDATE "
                    "  SET limit_value = EXCLUDED.limit_value, "
                    "      unit = EXCLUDED.unit"
                ),
                {"p": pid, "f": feature, "l": limit, "u": unit},
            )
    return plan_ids


def _provision_workspaces_for_existing_users(
    conn, plan_ids: dict[str, object],
) -> None:
    free_plan_id = plan_ids["free"]
    user_rows = conn.execute(
        sa.text("SELECT id, email FROM users ORDER BY created_at, id")
    ).all()

    for uid, email in user_rows:
        local = (email or "user").split("@", 1)[0].strip() or "user"
        slug = _unique_slug(conn, local)
        name = (f"{local}'s workspace")[:120]

        ws_id = conn.execute(
            sa.text(
                "INSERT INTO workspaces "
                "(name, slug, owner_user_id, status) "
                "VALUES (:n, :s, :o, 'active') RETURNING id"
            ),
            {"n": name, "s": slug, "o": uid},
        ).scalar()

        conn.execute(
            sa.text(
                "INSERT INTO workspace_memberships "
                "(workspace_id, user_id, role, status) "
                "VALUES (:w, :u, 'owner', 'active')"
            ),
            {"w": ws_id, "u": uid},
        )

        conn.execute(
            sa.text(
                "INSERT INTO subscriptions "
                "(workspace_id, plan_id, status, provider) "
                "VALUES (:w, :p, 'active', 'none')"
            ),
            {"w": ws_id, "p": free_plan_id},
        )


def _backfill_projects(conn) -> None:
    """Attach each project to its owner's personal workspace.
    Requires projects.workspace_id to already exist."""
    conn.execute(
        sa.text(
            "UPDATE projects p "
            "SET workspace_id = m.workspace_id "
            "FROM workspace_memberships m "
            "WHERE m.user_id = p.user_id "
            "  AND m.role = 'owner' "
            "  AND m.status = 'active' "
            "  AND p.workspace_id IS NULL"
        )
    )


def _verify_invariants(conn) -> None:
    """Fail-hard verification. Any raise rolls back the whole
    migration transaction."""

    # (a) no orphan projects
    null_projects = conn.execute(
        sa.text("SELECT count(*) FROM projects WHERE workspace_id IS NULL")
    ).scalar()
    if null_projects:
        raise RuntimeError(
            f"migration 0032: {null_projects} projects have no workspace"
        )

    # (b) every workspace has exactly one active owner membership
    bad = conn.execute(
        sa.text(
            "SELECT w.id FROM workspaces w "
            "LEFT JOIN workspace_memberships m "
            "  ON m.workspace_id = w.id "
            " AND m.role = 'owner' "
            " AND m.status = 'active' "
            "GROUP BY w.id HAVING count(m.id) <> 1"
        )
    ).all()
    if bad:
        raise RuntimeError(
            f"migration 0032: {len(bad)} workspaces do not have "
            f"exactly one active owner"
        )

    # (c) workspaces.owner_user_id matches the active owner membership
    bad = conn.execute(
        sa.text(
            "SELECT w.id FROM workspaces w "
            "JOIN workspace_memberships m "
            "  ON m.workspace_id = w.id "
            " AND m.role = 'owner' "
            " AND m.status = 'active' "
            "WHERE w.owner_user_id <> m.user_id"
        )
    ).all()
    if bad:
        raise RuntimeError(
            f"migration 0032: {len(bad)} workspaces have owner_user_id "
            f"mismatched with their owner membership"
        )

    # (d) every workspace has exactly one live subscription
    bad = conn.execute(
        sa.text(
            "SELECT w.id FROM workspaces w "
            "LEFT JOIN subscriptions s "
            "  ON s.workspace_id = w.id "
            " AND s.status IN ('trialing','active','past_due') "
            "GROUP BY w.id HAVING count(s.id) <> 1"
        )
    ).all()
    if bad:
        raise RuntimeError(
            f"migration 0032: {len(bad)} workspaces do not have "
            f"exactly one live subscription"
        )

    # (e) each project's workspace owner matches the project's user
    bad = conn.execute(
        sa.text(
            "SELECT p.id FROM projects p "
            "JOIN workspace_memberships m "
            "  ON m.workspace_id = p.workspace_id "
            " AND m.role = 'owner' "
            " AND m.status = 'active' "
            "WHERE m.user_id <> p.user_id"
        )
    ).all()
    if bad:
        raise RuntimeError(
            f"migration 0032: {len(bad)} projects point at a workspace "
            f"not owned by their user"
        )


# ==========================================================================
# downgrade
# ==========================================================================

def downgrade() -> None:
    """Reverse M37. Data added by M37 is destroyed; original
    users/projects rows are preserved. See module docstring."""
    op.drop_index("ix_projects_workspace_status", table_name="projects")
    op.drop_index("ix_projects_workspace", table_name="projects")
    op.drop_constraint(
        "fk_projects_workspace", "projects", type_="foreignkey",
    )
    op.drop_column("projects", "workspace_id")

    op.drop_index("ix_billing_events_status", table_name="billing_events")
    op.drop_table("billing_events")

    op.drop_index("ix_usage_events_user", table_name="usage_events")
    op.drop_index(
        "ix_usage_events_ws_occurred", table_name="usage_events",
    )
    op.drop_index(
        "ix_usage_events_ws_metric_occurred",
        table_name="usage_events",
    )
    op.drop_index(
        "ux_usage_events_idempotency", table_name="usage_events",
    )
    op.drop_table("usage_events")

    op.drop_index(
        "ix_subscriptions_provider_customer",
        table_name="subscriptions",
    )
    op.drop_index(
        "ix_subscriptions_workspace", table_name="subscriptions",
    )
    op.drop_index(
        "ux_subscriptions_active_workspace",
        table_name="subscriptions",
    )
    op.drop_table("subscriptions")

    op.drop_index(
        "ix_plan_entitlements_plan", table_name="plan_entitlements",
    )
    op.drop_table("plan_entitlements")

    op.drop_index("ux_plans_code", table_name="plans")
    op.drop_table("plans")

    op.drop_index(
        "ix_workspace_invitations_email",
        table_name="workspace_invitations",
    )
    op.drop_index(
        "ix_workspace_invitations_ws_status",
        table_name="workspace_invitations",
    )
    op.drop_index(
        "ux_workspace_invitations_token_hash",
        table_name="workspace_invitations",
    )
    op.drop_table("workspace_invitations")

    op.drop_index(
        "ux_workspace_memberships_owner_active",
        table_name="workspace_memberships",
    )
    op.drop_index(
        "ix_workspace_memberships_user",
        table_name="workspace_memberships",
    )
    op.drop_index(
        "ix_workspace_memberships_ws",
        table_name="workspace_memberships",
    )
    op.drop_table("workspace_memberships")

    op.drop_index("ix_workspaces_status", table_name="workspaces")
    op.drop_index("ix_workspaces_owner", table_name="workspaces")
    op.drop_index("ux_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")